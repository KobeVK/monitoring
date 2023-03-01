import requests, sys , smtplib
from email.message import EmailMessage

dict_path = "out.txt"

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

# Find the last successful pipeline for the project
success_pipeline_url = f'{gitlab_url}/api/v4/projects/{project_id}/pipelines?status=success&source=web&source=push&ref={default_branch}'
success_response = requests.get(success_pipeline_url, headers={'Private-Token': personal_access_token})
success_pipelines = success_response.json()
last_successful_pipeline = success_pipelines[0]
last_successful_pipeline_time = last_successful_pipeline['updated_at']

# Find who merged but his pipeline failed and broke master
failed_pipeline_url = f'{gitlab_url}/api/v4/projects/{project_id}/pipelines?status=failed&source=web&source=push&ref={default_branch}'
fail_response = requests.get(failed_pipeline_url, headers={'Private-Token': personal_access_token})
fail_pipelines = fail_response.json()
last_failed_pipeline = fail_pipelines[0]
last_failed_pipeline_time = last_failed_pipeline['updated_at']
pipeline_url = last_failed_pipeline['web_url']

if last_failed_pipeline_time > last_successful_pipeline_time:
    # Find the commit that was associated with the pipeline who broke master
    commit_url = f'{gitlab_url}/api/v4/projects/{project_id}/repository/commits/{last_failed_pipeline["sha"]}'
    response = requests.get(commit_url, headers={'Private-Token': personal_access_token})
    commit = response.json()
    # Find the user who pushed the commit
    user = commit['author_name']
    email = commit['author_email']

    with open(dict_path, "w") as f:
        output = print(f'The user who broke {project_name} was {user}; a link to his pipeline -> {pipeline_url}')
        print(f'The user who broke {project_name} was {user}; a link to his pipeline -> {pipeline_url}', file =f)

        # Set the email server and login credentials
        server = smtplib.SMTP('mail.f5net.com')
        #server.login('k.vaknin@f5.com', 'Metallica00%%')

        # Set the email message
        subject = f' {default_branch} on {project_name} is broken!'
        body = f'Following an MR by {user}, {project_name}\'s {default_branch} might be broken;  \n a link to the pipeline -> {pipeline_url}'
        message = f'Subject: {subject}\n\n{body}'

        # Set the recipient and sender email addresses
        to_email = [masked]
        from_email = 'masked'
        # Send the email
        server.sendmail(from_email, to_email, message)

        # Close the server connection
        server.quit()
else:
    print(f"Nothing broke the last green pipeline yet!")

