import requests, sys , smtplib, json, os, subprocess
from email.message import EmailMessage
from sys import argv
from influxdb import InfluxDBClient
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import base64

class color:
   GREEN = '\033[92m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

dict_path = "out.txt"
def update_db(vertical_name, OS, status, failed_job_name, failed_job_reason, failed_job_url):
    client = InfluxDBClient(host="xx.xx.xx.xx",
                        port="8086",
                        username='xxxx',
                        password='xxxxxx',
                        database='nightly_tst'
                        )

    data = [
        {
            "measurement": "waf-ci-nightly5",
            "tags": {
                "Failed_Test": vertical_name
            },
            "fields": {
                "OS": OS,
                "Status": status,
                "Failed_stage": failed_job_name,
                "Failure_Reason": failed_job_reason,
                "URL": failed_job_url,
                "last_nginx_version": last_nginx_version,
                "last_engine_version": WAF_GENERAL_LAST_TAG_NAME,
                "last_nap_version": WAF_ON_NGINX_LAST_TAG_NAME,
                "pipeline_id": "6134068"
            }
        }
    ]
    client.write_points(data)
    client.close()

# Set your GitLab personal access token
personal_access_token =  'masked' #'YOUR_PERSONAL_ACCESS_TOKEN'

# Set the URL of the GitLab instance you want to use
gitlab_url = 'masked'

# Set project
project_id = sys.argv[1]
projects_api = f'{gitlab_url}/api/v4/projects/{project_id}'

# Get default branch for project
default_branch_response = requests.get(projects_api, headers={'Private-Token': personal_access_token})
default_branch_response_json = default_branch_response.json()
default_branch = default_branch_response_json['default_branch']
project_name = default_branch_response_json['name']

# Find the last pipeline for the project
success_pipeline_url = f'{gitlab_url}/api/v4/projects/{project_id}/pipelines?source=schedule&ref={default_branch}'
all_pipelines = requests.get(success_pipeline_url, headers={'Private-Token': personal_access_token})
scheduled_pipelines = all_pipelines.json()
last_pipeline = scheduled_pipelines[0]
last_pipeline_id = last_pipeline['id']
last_successful_pipeline_time = last_pipeline['updated_at'] #To DB

# Get versions
job_name = "get-last-tags" 
job_artifacts_url = f'{gitlab_url}/api/v4/projects/{project_id}/pipelines/{last_pipeline_id}/jobs/'
all_jobs = requests.get(job_artifacts_url, headers={'Private-Token': personal_access_token})
all_jobs_json = all_jobs.json()
for job in all_jobs_json:
    if job['stage'] == f'{job_name}':
        get_last_tag_job_id = job['id']
        break

CURL_CMD_FORMAT = f'curl --location --header "PRIVATE-TOKEN: {personal_access_token}" {gitlab_url}/api/v4/projects/{project_id}/jobs/{get_last_tag_job_id}/artifacts/tags.env -o tags'
curl_cmd = CURL_CMD_FORMAT.format(gitlab_url=gitlab_url)
result = subprocess.run(curl_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if result.returncode != 0:
    print("curl command failed")
    print(result.stderr)
else:
    with open("tags", "r") as file:
        for line in file:
            if "LAST_NGINX_VERSION=" in line:
                last_nginx_version = line.split("=")[1].strip()
            elif "WAF_GENERAL_LAST_TAG_NAME=" in line:
                WAF_GENERAL_LAST_TAG_NAME = line.split("=")[1].strip()
            elif "WAF_ON_NGINX_LAST_TAG_NAME=" in line:
                WAF_ON_NGINX_LAST_TAG_NAME = line.split("=")[1].strip()
                
#get downstream pipelines id's
downstream_pipelines = f'{gitlab_url}/api/v4/projects/{project_id}/pipelines/{last_pipeline_id}/bridges'
all_downstream_pipelines = requests.get(downstream_pipelines, headers={'Private-Token': personal_access_token})
downstream_pipelines_json = all_downstream_pipelines.json()

for vertical in downstream_pipelines_json:
    name = f"{vertical['name']}" #TO DB - vertical name
    id = vertical['downstream_pipeline']['id']
    v_project_id = vertical['downstream_pipeline']['project_id']
    v_status = vertical['downstream_pipeline']['status']
    #get functional tests id
    if vertical['name'] == "functional-tests":
        functional_tests_pipeline_id = vertical['downstream_pipeline']['id']

    #bridges
    url = f'{gitlab_url}/api/v4/projects/{v_project_id}/pipelines/{id}/bridges'
    vdp = requests.get(url, headers={'Private-Token': personal_access_token})
    vdp_json = vdp.json()
    for dp in vdp_json:
        dp_name = f"{dp['name']}" #TO DB - downstream pipeline name
        dp_status = f"{dp['downstream_pipeline']['status']}"#TO DB - downstream pipeline status

        if dp_status == "failed":
            dp_project_id = f"{dp['downstream_pipeline']['project_id']}"
            dp_id = f"{dp['downstream_pipeline']['id']}"
            dp_url = f'{gitlab_url}/api/v4/projects/{dp_project_id}/pipelines/{dp_id}/jobs?scope[]=failed'
            all_dp_json = requests.get(dp_url, headers={'Private-Token': personal_access_token})
            vdp_json = all_dp_json.json()
            for j in vdp_json:
                failed_job_name = f"{j['name']}" #TO DB
                failed_job_url = f"{j['web_url']}" #TO DB
                failed_job_reason = f"{j['failure_reason']}" #TO DB
                print(f"{name}:", f"{dp_name}:", dp_status, failed_job_name, failed_job_reason , failed_job_url ) #TO DB
                update_db(name,dp_name,dp_status,failed_job_name,failed_job_reason,failed_job_url)

    #non-bridges
    if v_status == "failed":
        v_name = f"{vertical['name']}" #to DB
        v_project_id = f"{vertical['downstream_pipeline']['project_id']}"
        v_pipeline_id = f"{vertical['downstream_pipeline']['id']}"
        v_url = f'{gitlab_url}/api/v4/projects/{v_project_id}/pipelines/{v_pipeline_id}/jobs?scope[]=failed'
        failed_verticals_json = requests.get(v_url, headers={'Private-Token': personal_access_token})
        failed_vJson = failed_verticals_json.json()
        for j in failed_vJson:
            failed_job_name = f"{j['name']}" #TO DB
            failed_job_url = f"{j['web_url']}" #TO DB
            failed_job_reason = f"{j['failure_reason']}" #TO DB
            print(v_name, failed_job_name, v_status, failed_job_reason, failed_job_url)
            update_db(v_name,failed_job_name, v_status,failed_job_name,failed_job_reason,failed_job_url)

#get efficacy status
efficacy_project_id = "13624"
functional_tests_url = f'{gitlab_url}/api/v4/projects/{project_id}/pipelines/{functional_tests_pipeline_id}/bridges'
functional_tests = requests.get(functional_tests_url, headers={'Private-Token': personal_access_token})
functional_tests_json = functional_tests.json()
for os in functional_tests_json:
    os_id = f"{os['downstream_pipeline']['id']}"
    os_status = f"{os['downstream_pipeline']['status']}"
    waf_nginx_test_pipeline_project_id = "14483"
    if os_status == "failed":
        failed_os_url = f'{gitlab_url}/api/v4/projects/{waf_nginx_test_pipeline_project_id}/pipelines/{os_id}/bridges'
        failed_os_url_request = requests.get(failed_os_url, headers={'Private-Token': personal_access_token})
        failed_os_url_json = failed_os_url_request.json()
        for f in failed_os_url_json:
            efficacy_status = f"{f['downstream_pipeline']['status']}" #status of each efficacy pipeline that was triggered from functional-tests
            if efficacy_status == "failed":
                operating_system_test = f"{os['name']}" #toDB
                operating_system = operating_system_test.replace("-test", "")
                efficacy_failed_pipeline_id = f"{f['downstream_pipeline']['id']}"
                efficacy_ds_url = f'{gitlab_url}/api/v4/projects/{efficacy_project_id}/pipelines/{efficacy_failed_pipeline_id}/jobs'
                efficacy_ds_url_request = requests.get(efficacy_ds_url, headers={'Private-Token': personal_access_token})
                efficacy_ds_json = efficacy_ds_url_request.json()
                for eff in efficacy_ds_json:
                    efficacy_job_status = f"{eff['status']}" #status of job in efficacy pipeline
                    if efficacy_job_status == "failed":
                        failed_efficacy_stage = f"{eff['name']}"
                        failed_efficacy_stage_parsed = failed_efficacy_stage.split(" ")[-2:]  # split the string by spaces and get the last two elements
                        failed_efficacy_stage_parsed_result = " ".join(failed_efficacy_stage_parsed)  # join the last two elements with a space
                        efficacy_failure_reason = f"{eff['failure_reason']}"
                        efficacy_web_url = f"{eff['web_url']}"
                        print("efficacy", operating_system, "failed" , failed_efficacy_stage_parsed_result, efficacy_failure_reason, efficacy_web_url )
                        update_db("efficacy", operating_system, "failed" , failed_efficacy_stage_parsed_result, efficacy_failure_reason, efficacy_web_url)

#get today's date
today = datetime.datetime.now().date()
date_suffix = 'th' if 11 <= today.day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(today.day % 10, 'th')
date_string = today.strftime("%b %d") + date_suffix + ", " + today.strftime("%Y")
    
#get dashboard screenshot
curl_command = "curl 'http://admin:Welcome01@10.240.105.123:8080/render/d/bvYeA9A4k/nightly-waf-ci?orgId=1&from=1675926420273&to=1675969620274&width=2000&height=1500' >> grafana.png"
subprocess.run(curl_command, shell=True, check=True)
with open("grafana.png", "rb") as image_file:
    img = MIMEImage(image_file.read(), _subtype="png")
    encoded_bytes = base64.b64encode(img.get_payload(decode=True))

msg = MIMEMultipart()
text = MIMEText(f'The Following dashboard shows pipeline status for: \n\n  Engine Version: {WAF_GENERAL_LAST_TAG_NAME} \n  NAP Version: {WAF_ON_NGINX_LAST_TAG_NAME} \n NGINX+ Version: {last_nginx_version} \n\n A link to the dashboard is available at \n http://10.240.105.123:8080/d/bvYeA9A4k/nightly-waf-ci?orgId=1&from=now-12h&to=now&kiosk')

msg.attach(text)

msg.attach(img)

msg['Subject'] = f'Pipelines status update, {date_string}'
msg['From'] = 'masked'
msg['To'] = 'masked'

s = smtplib.SMTP('masked')
s.sendmail(msg['From'], [msg['To']], msg.as_string())
s.quit()
