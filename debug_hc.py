import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

def main():
    options = Options()
    # options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    
    # Use one of the job URLs the user provided
    url = "https://hiring.cafe/viewjob/ust0epexijv2o79t"
    print(f"Loading {url}")
    driver.get(url)
    time.sleep(5)
    
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    
    # Print all links and buttons
    print("--- LINKS ---")
    for a in soup.find_all('a'):
        print(f"Link text: '{a.text.strip()}' href: {a.get('href')}")
        
    print("--- BUTTONS ---")
    for b in soup.find_all('button'):
        print(f"Button text: '{b.text.strip()}'")
        
    driver.quit()

if __name__ == "__main__":
    main()
