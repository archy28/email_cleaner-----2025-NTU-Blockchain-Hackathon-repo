from typing import Dict, Any

import requests, json, os

def test_prompt_llama():
    import requests
    import json
    from typing import Any

    class EmailClassifier:
        def __init__(self, base_url: str = "http://www-api.u2922889.nyat.app:45965/api/generate"):
            self.session = requests.Session()
            self.session.headers.update({
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            })
            self.base_url = base_url
            self.system_prompt = (
                "You are an email classifier. "
                "Return only one JSON object:\n"
                '{"primary":"<primary_tag>","secondary":"<secondary_tag>","reason":"<brief_reason>"}\n'
                "Primary tags: spam|event_important|event_optional|info|pin|academic|career|billing|it_security|health|research\n"
                "Secondary tags: deadline|mandatory|rsvp|workshop|social|phishing|newsletter|grade_posted|assignment_due|tuition|refund|security|cfp|expires_in_minutes|burn_after_reading\n"
            )

        def classify(self, email: dict[str, str]) -> dict[str, Any]:
            """
            email = {"sender": "...", "theme": "...", "content": "..."}
            """
            prompt = f"{self.system_prompt}\n\nEmail:\n{json.dumps(email)}"
            payload = {
                "model": "llama3:8b",
                "prompt": prompt,
                "format": "json",
                "options": {"temperature": 0.0, "num_predict": 64},
                "stream": False
            }
            try:
                r = self.session.post(self.base_url, json=payload, timeout=60)
                r.raise_for_status()
                return r.json()['response']
            except requests.RequestException as e:
                return {"primary": "Error", "secondary": "Network", "reason": str(e)}


    classifier = EmailClassifier()  # 初始化一次
    email = {
        "sender": "Job-In Fair Career Office",
        "theme": "NTU Job-In Fair 2025 - Job Opportunities & Workshop",
        "content": "Dear Students, Step into your future with an exciting range of career opportunities..."
    }
    print(classifier.classify(email))
test_prompt_llama()

def handle_email():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def gmail_service():
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=8080)
        return build('gmail', 'v1', credentials=creds)

    def fetch_latest_text(service, max_results=1):
        msgs = service.users().messages().list(userId='me', maxResults=max_results, q='is:unread -in:spam -in:trash').execute()
        if not msgs.get('messages'):
            return None
        msg = service.users().messages().get(userId='me', id=msgs['messages'][0]['id']).execute()
        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        subject = headers.get('Subject', '')
        sender  = headers.get('From', '')

        import base64
        def get_body(part):
            if part.get('mimeType') == 'text/plain':
                return base64.urlsafe_b64decode(part['body']['data']).decode()
            # if part.get('mimeType') == 'text/html': # 广告链接太多
            #     from bs4 import BeautifulSoup
            #     html = base64.urlsafe_b64decode(part['body']['data']).decode()
            #     return BeautifulSoup(html, 'lxml').get_text()
            for p in part.get('parts', []):
                res = get_body(p)
                if res:
                    return res
        body = get_body(msg['payload'])
        return {'subject': subject, 'from': sender, 'body': body}

    if __name__ == '__main__':
        svc = gmail_service()
        mail = fetch_latest_text(svc)
        print(mail)

def test_whole_route():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    import requests, json, os

    SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

    # ---------- Google 登录 ----------
    def gmail_service():
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=8080)
        return build('gmail', 'v1', credentials=creds)

    # ---------- 工具 ----------
    def list_labels(service):
        return {l['name']: l['id'] for l in service.users().labels().list(userId='me').execute().get('labels', [])}

    def create_label_if_needed(service, name):
        labels = list_labels(service)
        if name in labels:
            return labels[name]
        body = {'name': name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
        return service.users().labels().create(userId='me', body=body).execute()['id']

    def llama_classify(text: str) -> dict[str, Any]:
        """
        调用本地 Llama-3，返回 (一级, 二级, 理由)
        """
        print(text)
        prompt = (
            "You are an email classifier for university students. "
            "Return only one JSON line: {\"L1\":\"L1\",\"L2\":\"L2\",\"summary\":\"15-word summary\"} "
            "Labels L1:Study|Event|Career|Finance|Social|Admin|Spam|Pin "
            "Labels L2:Deadline|Assignment|Lecture|Grade|Workshop|Seminar|Club|CareerFair|Intern|Job|CV|Interview|Scholarship|Invoice|Refund|Alumni|Mentor|Registration|Policy|IT|Health|Ads|Phish|Newsletter|OTP|Alert|Burn "
            f"Email:{text}"
        )
        payload = {
            "model": "llama3:8b",
            "prompt": prompt,
            # "format": "json",  # 强制返回 JSON
            "options": {"temperature": 0.0, "num_predict": 64},
            "stream": False
        }
        r = requests.post("http://www-api.u2922889.nyat.app:45965/api/generate", json=payload, timeout=200,
                          headers={"ngrok-skip-browser-warning": "1", 'User-Agent': 'Mozilla/5.0'})
        data = r.json()['response']
        print(data)
        # return {'tag1': data['L1'], 'tag2': data['L2'], 'summary': data['reason']}
        return data
    # ---------- 主流程 ----------
    def main(service, max_results=10):
        msgs = service.users().messages().list(userId='me', maxResults=max_results, q='is:unread in:inbox').execute()
        for m in msgs.get('messages', []):
            mid   = m['id']
            msg   = service.users().messages().get(userId='me', id=mid, format='full').execute()
            body    = get_plain_body(msg)
            print("resolve all the information for the email----------------")
            l1, l2, reason = llama_classify(f"{body}")
            label_name  = f"{l1}/{l2}"        # 例如 "Study/Deadline"
            label_id    = create_label_if_needed(service, label_name)

            # 打标签 + 标已读
            service.users().messages().modify(
                userId='me',
                id=mid,
                # body={'addLabelIds': [label_id], 'removeLabelIds': ['UNREAD']}
                body = {'addLabelIds': [label_id]}
            ).execute()
            print(f"{label_name} ({reason})")

    def get_plain_body(msg):
        import base64
        def _extract(part):
            mime = part.get('mimeType')
            if mime == 'text/plain':
                return base64.urlsafe_b64decode(part['body']['data']).decode(errors='ignore')
            # if mime == 'text/html':
            #     from bs4 import BeautifulSoup
            #     html = base64.urlsafe_b64decode(part['body']['data']).decode(errors='ignore')
            #     return BeautifulSoup(html, 'lxml').get_text()
            for p in part.get('parts', []):
                res = _extract(p)
                if res:
                    return res
            return ''
        return _extract(msg['payload'])

    # # ---------- 运行 ----------
    # if __name__ == '__main__':
    #     main(gmail_service())