-- Refine Infosys Selectors in the database
-- Focus only on Infosys selectors

SET @job_site_id = (SELECT id FROM job_sites WHERE domain = 'digitalcareers.infosys.com' LIMIT 1);

-- Update the existing entry or insert a new one if it somehow went missing
INSERT INTO `site_selectors` (`job_site_id`, `type`, `config_json`)
VALUES (
    @job_site_id,
    'application',
    '{
      "search": {
        "keyword": "ai engineers",
        "location": "USA",
        "reveal_buttons": [
          ["xpath", "//button[contains(translate(., \'ABCDEFGHIJKLMNOPQRSTUVWXYZ\', \'abcdefghijklmnopqrstuvwxyz\'), \'search jobs\')]"],
          ["xpath", "//button[contains(.,\'SEARCH\')]"],
          ["css selector", ".search-btn"],
          ["css selector", ".js_search_cp_jobs"]
        ],
        "input_box": [
          ["name", "keyWordSearch"],
          ["css selector", "input[name=\'keyWordSearch\']"],
          ["css selector", "input[aria-label*=\'keywords\']"],
          ["css selector", "input.search"],
          ["css selector", "input.js_search_cp_jobs"],
          ["css selector", "input[placeholder*=\'Search\']"],
          ["css selector", "input[type=\'search\']"],
          ["xpath", "//input[contains(@placeholder,\'Search\') or contains(@aria-label,\'Search\')]"]
        ],
        "job_links": [
          ["css selector", "a[href*=\'job\']"],
          ["css selector", "a[href*=\'careers\']"],
          ["xpath", "//a[contains(@href,\'job\') or contains(@href,\'careers\')]"]
        ]
      },
      "apply": {
        "apply_button": [
          ["css selector", ".infosys-apply-link"],
          ["xpath", "//a[contains(@href, \'apply-\')]"],
          ["xpath", "//button[contains(.,\'Apply\')]"],
          ["xpath", "//a[contains(.,\'Apply\')]"],
          ["xpath", "//button[contains(.,\'Apply now\') or contains(.,\'Apply Now\')]"],
          ["css selector", "a[href*=\'apply\'], button[class*=\'apply\']"]
        ],
        "first_time_button": [
          ["css selector", ".apply-first-time-button"],
          ["xpath", "//button[contains(.,\'applying for the first time\')]"]
        ],
        "proceed_button": [
           ["id", "proceed-navigation"],
           ["link text", "Proceed"],
           ["xpath", "//a[contains(.,\'Proceed\')]"],
           ["xpath", "//button[contains(.,\'Proceed\')]"]
        ],
        "form_signals": [
          ["css selector", "input[type=\'file\']"],
          ["css selector", "input#firstname"],
          ["css selector", "input#email"],
          ["xpath", "//input[@type=\'email\' or contains(@aria-label,\'Email\') or contains(@placeholder,\'Email\')]"],
          ["xpath", "//input[contains(@aria-label,\'First\') or contains(@placeholder,\'First\')]"]
        ]
      },
      "popups": {
        "close_buttons": [
          ["css selector", "button.close[data-dismiss=\'modal\']"],
          ["css selector", ".x-icon"],
          ["css selector", ".close-item button.close"],
          ["xpath", "//button[contains(@class,\'close\')][@data-dismiss=\'modal\']"],
          ["xpath", "//span[@class=\'x-icon\']"],
          ["css selector", ".modal-close-button"],
          ["css selector", ".close-icon"],
          ["css selector", "[class*=\'close\']"],
          ["xpath", "//button[contains(.,\'Close\')]"],
          ["xpath", "//button[contains(.,\'Cancel\')]"],
          ["xpath", "//button[contains(.,\'Skip\')]"],
          ["xpath", "//a[contains(.,\'Close\')]"],
          ["xpath", "//span[contains(.,\'Close\')]"],
          ["xpath", "//button[contains(.,\'Done\')]"]
        ]
      },
      "personal_form": {
        "firstname": [["id", "firstname"], ["xpath", "//input[contains(@id,\'first_name\') or contains(@id,\'firstname\') or contains(@aria-label,\'First\')]"]],
        "lastname": [["id", "lastname"], ["xpath", "//input[contains(@id,\'last_name\') or contains(@id,\'lastname\') or contains(@aria-label,\'Last\')]"]],
        "email": [["id", "email"], ["xpath", "//input[@type=\'email\' or contains(@id,\'email\')]"]],
        "phone": [["id", "phone"], ["xpath", "//input[contains(@id,\'phone\') or contains(@aria-label,\'Phone\')]"]],
        "address": [["id", "address_1"], ["xpath", "//input[contains(@id,\'address\')]"]],
        "city": [["id", "city"], ["xpath", "//input[contains(@id,\'city\')]"]],
        "zip": [["id", "zipcode"], ["xpath", "//input[contains(@id,\'zip\') or contains(@id,\'zipcode\') or contains(@aria-label,\'Zip\')]"]],
        "country": [["id", "country"], ["xpath", "//select[contains(@name,\'country\') or contains(@id,\'country\')]"]],
        "state": [["id", "state"], ["xpath", "//select[contains(@name,\'state\') or contains(@id,\'state\')]"]]
      },
      "education_form": {
        "school": [["name", "custom[education][0][school]"], ["css selector", "input[name*=\'school\']"], ["xpath", "//input[contains(@placeholder,\'School\') or contains(@placeholder,\'education institution\')]"], ["id", "school"]],
        "grad_year": [["name", "custom[education][0][graduation_year]"], ["css selector", "input[name*=\'graduation\']"], ["css selector", "select[name*=\'graduation\']"], ["xpath", "//input[contains(@placeholder,\'Year\') or contains(@placeholder,\'graduation\')]"], ["id", "graduation_year"]],
        "study_area": [["name", "custom[education][0][study_area]"], ["css selector", "input[name*=\'study\']"], ["xpath", "//input[contains(@placeholder,\'study\') or contains(@placeholder,\'Area of study\')]"], ["id", "area_of_study"]],
        "gpa": [["name", "custom[education][0][gpa]"], ["css selector", "input[name*=\'gpa\']"], ["xpath", "//input[contains(@placeholder,\'GPA\') or contains(@placeholder,\'gpa\')]"], ["id", "gpa"]],
        "degree": [["name", "custom[education][0][degree]"], ["css selector", "select[name*=\'degree\']"], ["css selector", "select[name*=\'education_level\']"], ["xpath", "//select[contains(@placeholder,\'degree\') or contains(@placeholder,\'Degree\')]"], ["id", "degree"]]
      },
      "work_form": {
        "company": [["name", "custom[work][{idx}][company]"], ["css selector", "input[name*=\'work\'][name*=\'company\']"], ["xpath", "//input[contains(@placeholder,\'Company\')]"]],
        "title": [["name", "custom[work][{idx}][job_title]"], ["css selector", "input[name*=\'work\'][name*=\'job_title\']"], ["xpath", "//input[contains(@placeholder,\'Job title\')]"]],
        "start_year": [["name", "custom[work][{idx}][start_year]"], ["css selector", "input[name*=\'work\'][name*=\'start_year\']"], ["xpath", "//input[contains(@placeholder,\'Start year\')]"]],
        "end_year": [["name", "custom[work][{idx}][end_year]"]],
        "current_job": [["name", "custom[work][0][current_job]"]],
        "add_button": [
          ["css selector", "p.add-more-trigger.work"],
          ["xpath", "//span[contains(.,\'+ Add other work experience\')]"],
          ["xpath", "//button[contains(.,\'Add\') and contains(.,\'Work\')]"],
          ["css selector", "button[class*=\'add\']"],
          ["xpath", "//button[normalize-space()=\'+\']"]
        ]
      },
      "navigation": {
        "next": [
          ["id", "forward-navigation"],
          ["css selector", ".form-next-button"],
          ["css selector", "button[class*=\'next\']"],
          ["css selector", "button[class*=\'continue\']"],
          ["xpath", "//button[contains(.,\'Next\') or contains(.,\'Continue\')]"],
          ["xpath", "//a[contains(.,\'Next\') or contains(.,\'Continue\')]"],
          ["id", "next"]
        ]
      },
      "eeo": {
        "next": [
            ["xpath", "//button[normalize-space()=\'Next\']"],
            ["xpath", "//a[normalize-space()=\'Next\']"],
            ["xpath", "//button[contains(.,\'Next\')]"],
            ["xpath", "//a[contains(.,\'Next\')]"],
            ["xpath", "//button[contains(.,\'Continue\')]"],
            ["xpath", "//a[contains(.,\'Continue\')]"],
            ["css selector", "button[type=\'submit\']"],
            ["css selector", "button.next-step"],
            ["id", "next"]
        ],
        "signature": [
          ["xpath", "//input[contains(@aria-label,\'Legal Name\') or contains(@title,\'Legal Name\')]"],
          ["xpath", "//input[contains(@aria-label,\'Full Name\') or contains(@title,\'Full Name\')]"],
          ["xpath", "//input[contains(@aria-label,\'Signature\') or contains(@title,\'Signature\')]"],
          ["xpath", "//input[contains(@aria-label,\'Digital Signature\') or contains(@title,\'Digital Signature\')]"],
          ["xpath", "//label[contains(.,\'Legal Name\')]/following::input[1]"],
          ["xpath", "//span[contains(.,\'Legal Name\')]/following::input[1]"]
        ]
      },
      "agreement": {
        "contract_restriction": ["xpath", "//input[@name=\'custom[other][contract_restriction]\']"],
        "source": [
          ["xpath", "//select[contains(@name, \'source\') or contains(@aria-label, \'hear about\')]"],
          ["xpath", "//label[contains(.,\'hear about us\')]/following::select[1]"],
          ["xpath", "//span[contains(.,\'hear about us\')]/following::select[1]"]
        ],
        "special_dropdowns": {
           "authorized": ["xpath", "//select[@name=\'custom[other][authorized]\']"],
           "degree": ["xpath", "//select[@name=\'custom[other][degree]\']"],
           "relocate": ["xpath", "//select[@name=\'custom[other][relocate]\']"],
           "travel": ["xpath", "//select[@name=\'custom[other][travel]\']"],
           "sponsorship": ["xpath", "//select[@name=\'custom[other][sponsorship]\']"]
        },
        "arbitration": ["xpath", "//input[@name=\'custom[other][arbitration]\' and @value=\'1\']"]
      },
      "submit": {
        "submit_button": [
          ["css selector", "a.form-submit-button"],
          ["xpath", "//a[contains(.,\'Apply now\')]"],
          ["xpath", "//button[contains(.,\'Submit\')]"],
          ["xpath", "//button[contains(.,\'Finish\') or contains(.,\'Complete\')]"],
          ["xpath", "//input[@type=\'submit\']"]
        ]
      }
    }\'
)
ON DUPLICATE KEY UPDATE `config_json`=VALUES(`config_json`);
