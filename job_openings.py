import requests
import time
import csv
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import logging
import sys
import json
import os
from abc import ABC, abstractmethod

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('job_scraper.log')
    ]
)
logger = logging.getLogger(__name__)

class JobScraperException(Exception):
    """自定义异常类用于处理爬虫相关错误"""
    pass

@dataclass
class JobPosting:
    """职位信息数据类"""
    company: str
    title: str
    level: str
    team: str
    location: str
    url: str

class CompanyConfig:
    """公司配置类"""
    def __init__(self, url: str, api: bool = True, is_av: bool = False, min_level: Optional[str] = None):
        self.url = url
        self.api = api
        self.is_av = is_av
        self.min_level = min_level

# 公司配置
COMPANY_CONFIGS = {
    "Waymo": CompanyConfig(
        url="https://boards-api.greenhouse.io/v1/boards/waymo/jobs",
        api=True,
        is_av=True
    ),
    "StackAV": CompanyConfig(
        url="https://boards-api.greenhouse.io/v1/boards/stackav/jobs",
        api=True,
        is_av=True
    ),
    "NVIDIA": CompanyConfig(
        url="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
        api=True,
        is_av=False,
        min_level="senior"
    ),
    "Scale": CompanyConfig(
        url="https://boards-api.greenhouse.io/v1/boards/scaleai/jobs",
        api=True,
        is_av=False
    ),
    "Databricks": CompanyConfig(
        url="https://boards-api.greenhouse.io/v1/boards/databricks/jobs",
        api=True,
        is_av=False
    )
}

class WebDriverManager:
    """WebDriver管理类"""
    @staticmethod
    def setup_driver(headless: bool = True) -> webdriver.Chrome:
        """设置并返回Chrome WebDriver"""
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)
            
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })
            
            return driver
        except Exception as e:
            raise JobScraperException(f"设置WebDriver时出错: {str(e)}")

class JobScraper(ABC):
    """抽象基类用于定义职位爬虫接口"""
    def __init__(self, company: str, config: CompanyConfig):
        self.company = company
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{company}")

    @abstractmethod
    def scrape_jobs(self) -> List[JobPosting]:
        """抓取职位的抽象方法"""
        pass

class GreenhouseJobScraper(JobScraper):
    """Greenhouse API职位爬虫"""
    def __init__(self, company: str, config: CompanyConfig):
        super().__init__(company, config)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
            'Accept': 'application/json'
        }

    def scrape_jobs(self) -> List[JobPosting]:
        try:
            self.logger.info(f"正在从{self.company} Greenhouse API获取职位信息")
            response = requests.get(self.config.url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for job in data.get("jobs", []):
                title = job.get("title", "")
                departments = job.get("departments", [])
                team = departments[0].get("name", "") if departments else ""
                offices = job.get("offices", [])
                location = offices[0].get("name", "") if offices else ""
                job_url = job.get("absolute_url", "")
                
                job_posting = JobPosting(
                    company=self.company,
                    title=title,
                    level=title,
                    team=team,
                    location=location,
                    url=job_url
                )
                jobs.append(job_posting)
                self.logger.info(f"已找到职位: {title}")
            
            return jobs
            
        except Exception as e:
            raise JobScraperException(f"从{self.company} Greenhouse API获取职位时出错: {str(e)}")

class WorkdayJobScraper(JobScraper):
    """Workday职位爬虫"""
    def __init__(self, company: str, config: CompanyConfig):
        super().__init__(company, config)
        self.driver = WebDriverManager.setup_driver()

    def scrape_jobs(self) -> List[JobPosting]:
        try:
            self.logger.info(f"正在从{self.company} Workday网站获取职位信息")
            self.driver.get(self.config.url)
            time.sleep(5)  # 等待页面加载
            
            jobs = []
            try:
                # 等待职位列表加载
                job_elements = WebDriverWait(self.driver, 30).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-automation-id='jobTitle']"))
                )
                
                for job_element in job_elements:
                    try:
                        title = job_element.text
                        url = job_element.get_attribute("href")
                        
                        # 点击职位获取详细信息
                        job_element.click()
                        time.sleep(2)
                        
                        # 获取团队信息
                        team = ""
                        try:
                            team_element = WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-automation-id='jobPostingLocation']"))
                            )
                            team = team_element.text
                        except:
                            pass
                            
                        # 获取地点信息
                        location = ""
                        try:
                            location_element = WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-automation-id='jobPostingLocation']"))
                            )
                            location = location_element.text
                        except:
                            pass
                            
                        job_posting = JobPosting(
                            company=self.company,
                            title=title,
                            level=title,
                            team=team,
                            location=location,
                            url=url
                        )
                        jobs.append(job_posting)
                        self.logger.info(f"已找到职位: {title}")
                        
                    except Exception as e:
                        self.logger.error(f"处理职位时出错: {str(e)}")
                        continue
                        
            except TimeoutException:
                self.logger.error("等待职位列表超时")
                
            return jobs
            
        except Exception as e:
            raise JobScraperException(f"从{self.company} Workday网站获取职位时出错: {str(e)}")
            
        finally:
            if self.driver:
                self.driver.quit()

class JobFilter:
    """职位过滤器类"""
    def __init__(self):
        self.level_keywords = ["staff", "l6", "grade 6", "ic6"]
        self.title_keywords = [
            "software engineer", "software", "engineer",
            "data scientist", "research scientist",
            "machine learning"
        ]
        self.logger = logging.getLogger(f"{__name__}.JobFilter")

    def filter_jobs(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """根据条件过滤职位"""
        filtered_jobs = []
        
        for job in jobs:
            title = job.title.lower()
            level = job.level.lower()
            
            self.logger.debug(f"\nDetailed job analysis:")
            self.logger.debug(f"Title: {job.title}")
            self.logger.debug(f"Level: {job.level}")
            self.logger.debug(f"Team: {job.team}")
            
            if any(keyword in title.lower() for keyword in ["intern", "internship"]):
                self.logger.debug("Skipping internship position")
                continue
                
            level_match = any(keyword in level for keyword in self.level_keywords)
            level_keywords_found = [keyword for keyword in self.level_keywords if keyword in level]
            self.logger.debug(f"Level keywords found: {level_keywords_found}")
            self.logger.debug(f"Level match: {level_match}")
            
            title_match = any(keyword in title for keyword in self.title_keywords)
            title_keywords_found = [keyword for keyword in self.title_keywords if keyword in title]
            self.logger.debug(f"Title keywords found: {title_keywords_found}")
            self.logger.debug(f"Title match: {title_match}")
            
            if level_match and title_match:
                filtered_jobs.append(job)
        
        return filtered_jobs

class JobStorage:
    """职位存储类"""
    def __init__(self, filename: str = "job_openings.csv"):
        self.filename = filename
        self.logger = logging.getLogger(f"{__name__}.JobStorage")

    def save_jobs(self, jobs: List[JobPosting]) -> None:
        """保存职位到CSV文件"""
        if not jobs:
            self.logger.warning("没有找到匹配的职位")
            return
        
        df = pd.DataFrame([vars(job) for job in jobs])
        df.to_csv(self.filename, index=False)
        self.logger.info(f"已将结果保存到 {self.filename}")

class JobScraperApp:
    """主应用类"""
    def __init__(self):
        self.driver = None
        self.job_filter = JobFilter()
        self.job_storage = JobStorage()
        self.logger = logging.getLogger(f"{__name__}.JobScraperApp")

    def run(self):
        """运行爬虫应用"""
        all_jobs = []
        
        try:
            for company, config in COMPANY_CONFIGS.items():
                try:
                    if company == "NVIDIA":
                        scraper = WorkdayJobScraper(company, config)
                    else:
                        scraper = GreenhouseJobScraper(company, config)
                        
                    jobs = scraper.scrape_jobs()
                    self.logger.info(f"从{company}找到 {len(jobs)} 个职位")
                    all_jobs.extend(jobs)
                except JobScraperException as e:
                    self.logger.error(f"抓取{company}职位时出错: {str(e)}")
            
            filtered_jobs = self.job_filter.filter_jobs(all_jobs)
            self.logger.info(f"找到 {len(filtered_jobs)} 个匹配的职位")
            
            self.job_storage.save_jobs(filtered_jobs)
            
            print(f"\nTotal: Found {len(filtered_jobs)} matching positions. Results saved to job_openings.csv")
            
        except Exception as e:
            self.logger.error(f"运行过程中出错: {str(e)}")

if __name__ == "__main__":
    app = JobScraperApp()
    app.run()
