import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

opt = uc.ChromeOptions()
opt.add_argument('--headless')
driver = uc.Chrome(options=opt)
try:
    driver.get('https://collabera.com/job-description/?post=368301')
    time.sleep(5)
    
    apply_btn = driver.find_element(By.CSS_SELECTOR, 'button.apply')
    apply_btn.click()
    time.sleep(3)
    
    inputs = driver.find_elements(By.TAG_NAME, 'input')
    print("=== INPUTS ===")
    for inp in inputs:
        print(inp.get_attribute('id'), inp.get_attribute('name'), inp.get_attribute('type'))
    print("=== LABELS ===")
    labels = driver.find_elements(By.TAG_NAME, 'label')
    for lbl in labels:
        print(lbl.get_attribute('for'), lbl.text)
        
finally:
    driver.quit()
