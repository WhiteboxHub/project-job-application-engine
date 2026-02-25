import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

def main():
    options = Options()
    driver = webdriver.Chrome(options=options)
    
    # Use one of the Ashby job URLs from the user's data
    # First go to a HiringCafe job that links to Ashby
    url = "https://hiring.cafe/viewjob/ust0epexijv2o79t"
    print(f"Loading {url}")
    driver.get(url)
    time.sleep(5)
    
    # Click Apply now button
    apply_btns = driver.find_elements(By.XPATH,
        "//*[self::a or self::button][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]")
    
    if apply_btns:
        print(f"Found {len(apply_btns)} apply buttons")
        for btn in apply_btns:
            print(f"  Button: '{btn.text.strip()}' tag={btn.tag_name} href={btn.get_attribute('href')}")
        driver.execute_script("arguments[0].click();", apply_btns[0])
        time.sleep(3)
    
    # Switch to new tab if opened
    if len(driver.window_handles) > 1:
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(3)
    
    current_url = driver.current_url
    print(f"\nCurrent URL: {current_url}")
    
    # Now click Apply on the Ashby page
    apply_btns2 = driver.find_elements(By.XPATH,
        "//*[self::a or self::button][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]")
    if apply_btns2:
        print(f"\nFound {len(apply_btns2)} apply buttons on Ashby page")
        driver.execute_script("arguments[0].click();", apply_btns2[0])
        time.sleep(5)
    
    print("\n=== ALL INPUTS (with form) ===")
    form_inputs = driver.find_elements(By.CSS_SELECTOR, "form input, form textarea, form select")
    print(f"Found {len(form_inputs)} form inputs")
    for inp in form_inputs:
        print(f"  tag={inp.tag_name} type={inp.get_attribute('type')} name={inp.get_attribute('name')} id={inp.get_attribute('id')} placeholder={inp.get_attribute('placeholder')} required={inp.get_attribute('required')}")
    
    print("\n=== ALL INPUTS (without form) ===")
    all_inputs = driver.find_elements(By.CSS_SELECTOR, "input, textarea, select")
    print(f"Found {len(all_inputs)} total inputs")
    for inp in all_inputs:
        print(f"  tag={inp.tag_name} type={inp.get_attribute('type')} name={inp.get_attribute('name')} id={inp.get_attribute('id')} placeholder={inp.get_attribute('placeholder')} aria-label={inp.get_attribute('aria-label')} required={inp.get_attribute('required')}")

    print("\n=== ALL LABELS ===")
    labels = driver.find_elements(By.CSS_SELECTOR, "label")
    for lbl in labels:
        print(f"  for={lbl.get_attribute('for')} text='{lbl.text.strip()}'")
    
    print("\n=== DIVS WITH CONTENTEDITABLE ===")
    editables = driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
    print(f"Found {len(editables)} contenteditable elements")
    
    input("Press ENTER to close browser...")
    driver.quit()

if __name__ == "__main__":
    main()
