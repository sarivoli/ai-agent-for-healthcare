from google.adk.agents import LlmAgent

finanace_assistence_agent = LlmAgent(name="finance_assistance_agent",
model="gemini-3.6-flash",
description="A simple finance assistance that helps with users finance goals",
instruction=""" You are a friendly finance assistant.
You can help answer user's generic quesiton on financne and help plan their finance goals, Be more friendly and positive. """)

root_agent = finanace_assistence_agent
