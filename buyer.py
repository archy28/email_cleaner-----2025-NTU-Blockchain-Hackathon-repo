import json
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

from virtuals_acp import ACPMemo
from virtuals_acp.client import VirtualsACP
from virtuals_acp.env import EnvSettings
from virtuals_acp.job import ACPJob
from virtuals_acp.models import ACPAgentSort, ACPJobPhase, ACPGraduationStatus, ACPOnlineStatus

load_dotenv(override=True)


def buyer(use_thread_lock: bool = True):
    env = EnvSettings()

    if env.WHITELISTED_WALLET_PRIVATE_KEY is None:
        raise ValueError("WHITELISTED_WALLET_PRIVATE_KEY is not set")
    if env.BUYER_AGENT_WALLET_ADDRESS is None:
        raise ValueError("BUYER_AGENT_WALLET_ADDRESS is not set")
    # if env.BUYER_ENTITY_ID is None:
    #     raise ValueError("BUYER_ENTITY_ID is not set")

    job_queue = deque()
    job_queue_lock = threading.Lock()
    initiate_job_lock = threading.Lock()
    job_event = threading.Event()

    def safe_append_job(job, memo_to_sign: Optional[ACPMemo] = None):
        if use_thread_lock:
            print(f"[safe_append_job] Acquiring lock to append job {job.id}")
            with job_queue_lock:
                print(f"[safe_append_job] Lock acquired, appending job {job.id} to queue")
                job_queue.append((job, memo_to_sign))
        else:
            job_queue.append((job, memo_to_sign))

    def safe_pop_job():
        """Modified to return both job and memo_to_sign"""
        if use_thread_lock:
            print(f"[safe_pop_job] Acquiring lock to pop job")
            with job_queue_lock:
                if job_queue:
                    job, memo_to_sign = job_queue.popleft()
                    print(f"[safe_pop_job] Lock acquired, popped job {job.id}")
                    return job, memo_to_sign
                else:
                    print("[safe_pop_job] Queue is empty after acquiring lock")
        else:
            if job_queue:
                job, memo_to_sign = job_queue.popleft()
                print(f"[safe_pop_job] Popped job {job.id} without lock")
                return job, memo_to_sign
            else:
                print("[safe_pop_job] Queue is empty (no lock)")
        return None, None

    def job_worker():
        while True:
            job_event.wait()
            while True:
                job, memo_to_sign = safe_pop_job()
                if not job:
                    break
                try:
                    process_job(job, memo_to_sign)
                except Exception as e:
                    print(f"\u274c Error processing job: {e}")
            if use_thread_lock:
                with job_queue_lock:
                    if not job_queue:
                        job_event.clear()
            else:
                if not job_queue:
                    job_event.clear()

    def on_new_task(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        print(f"[on_new_task] Received job {job.id} (phase: {job.phase})")
        safe_append_job(job, memo_to_sign)
        job_event.set()

    def on_evaluate(job: ACPJob):
        print("Evaluation function called", job.memos)
        for memo in job.memos:
            if memo.next_phase == ACPJobPhase.COMPLETED:
                callback_result = memo.content
                print(callback_result)
                job.evaluate(True)
                break

    def process_job(job: ACPJob, memo_to_sign: Optional[ACPMemo] = None):
        if job.phase == ACPJobPhase.NEGOTIATION:
            for memo in job.memos:
                if memo.next_phase == ACPJobPhase.TRANSACTION:
                    print("Paying job", job.id)
                    job.pay(job.price)
                    break
        elif job.phase == ACPJobPhase.COMPLETED:
            print("Job completed", job)
        elif job.phase == ACPJobPhase.REJECTED:
            print("Job rejected", job)

    threading.Thread(target=job_worker, daemon=True).start()

    acp = VirtualsACP(
        wallet_private_key=env.WHITELISTED_WALLET_PRIVATE_KEY,
        agent_wallet_address=env.BUYER_AGENT_WALLET_ADDRESS,
        on_new_task=on_new_task,
        on_evaluate=on_evaluate,
        entity_id=env.BUYER_ENTITY_ID
    )

    # Browse available agents based on a keyword and cluster name
    relevant_agents = acp.browse_agents(
        keyword="Email Classifier",
        # cluster="<your_cluster_name>",
        sort_by=[
            ACPAgentSort.SUCCESSFUL_JOB_COUNT,
        ],
        top_k=5,
        graduation_status=ACPGraduationStatus.ALL,
        online_status=ACPOnlineStatus.ALL
    )
    print(f"Relevant agents: {relevant_agents}")

    # Pick one of the agents based on your criteria (in this example we just pick the first one)
    chosen_agent = relevant_agents[0]

    # Pick one of the service offerings based on your criteria (in this example we just pick the first one)
    chosen_job_offering = chosen_agent.offerings[0]

    # email_json = json.dumps({'sender': 'sender1', 'theme': 'test', 'content': 'this is for test only'})
    email_json = json.dumps({
        "sender": "Job-In Fair Career Office",
        "theme": "NTU Job-In Fair 2025 - Job Opportunities & Workshop",
        "content": "Dear Students, Step into your future with an exciting range of career opportunities..."
    })
    # email_json = json.dumps({
    #     "sender": "Associate Vice President (Wellbeing)",
    #     "theme": "Be a PFA Champion !",
    #     "content": "Hey students,Do you know someone who may be struggling — a friend feeling overwhelmed, a peer growing distant, or someone quietly going through a tough time?'\Be a PFA Champion'\ is your opportunity to step up and make a difference. Psychological First Aid (PFA) is about offering comfort, listening with empathy, and providing support to someone experiencing distress in life. With PFA skills, we will be better able to look out for and support one another.Join us in these upcoming PFA activities and be part of building up a stronger, caring #OneNTU community!"
    # })
    # email_json = json.dumps({
    #     "sender": "Microsoft Azure",
    #     "theme": "Welcome to your Azure free account",
    #     "content": "You’re receiving this email because you recently signed up for an Azure free account. You now have access to 12 months of free services and a USD200* credit. To get started with this service, log in to your account."
    # })
    # email_json = json.dumps({
    #     "sender": "Assoc Prof",
    #     "theme": "Reminder: quiz 1",
    #     "content": "Hi all, A reminder for the upcoming quiz tomorrow at LT3: We will start at 6:45 PM and the quiz lasts for 30 mins The quiz is closed-book and on-paper, so please bring a pen In case you cannot come due to medical reasons, please provide an MC"
    # })
    # email_json = json.dumps({
    #     "sender": "PEH CHOON MENG (BAI JUNMING)",
    #     "theme": "Join the NTU x Base Hackathon Telegram Channel ",
    #     "content": "Hi everyone, Welcome to the NTU x Base Hackathon 2025! 🎉 We’ll be using our official Telegram channel for all updates, announcements and Q&A throughout the hackathon. Join here 👉 https://t.me/+ISTDKDo4NB1iZjRl In the channel, you’ll get: 📢 Event announcements & reminders ❓ A place where people can ask general and track-specific questions 💻 The virtual meeting link for Kickoff Day and workshops Make sure you join early so you don’t miss anything before Kickoff Day on 16 August 2025.See you there! 🚀 Best Regards, NTU x Base Hackathon Organising Team"
    # })
    incomplete_json = json.dumps({
        "sender": "my mom",
        "theme": "where is the restaurant?",
        "content": ""
    })
    unrelated_json = json.dumps({
        "sender": "Bob",
        "theme": "homework!",
        "content": "how to understand the Blockchain whitepaper?"
    })
    # email_json = unrelated_json

    with initiate_job_lock:
        job_id = chosen_job_offering.initiate_job(
            # <your_schema_field> can be found in your ACP Visualiser's "Edit Service" pop-up.
            # Reference: (./images/specify_requirement_toggle_switch.png)

            service_requirement={"email_body": email_json},
            evaluator_address=env.BUYER_AGENT_WALLET_ADDRESS,
            expired_at=datetime.now() + timedelta(days=1)
        )
        print(f"Job {job_id} initiated.")

    print("Listening for next steps...")
    threading.Event().wait()


if __name__ == "__main__":
    buyer()
