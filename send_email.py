import os
import smtplib
import pandas as pd
from email.message import EmailMessage
from datetime import date

CSV_PATH = "output/events.csv"
XLSX_PATH = f"output/KOMU-SportsData-{date.today()}.xlsx"

EMAIL_FROM = os.environ["EMAIL_FROM"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_TO = os.environ["EMAIL_TO"]

# Convert CSV to Excel
df = pd.read_csv(CSV_PATH)
df.to_excel(XLSX_PATH, index=False)

# Build email
msg = EmailMessage()
msg["Subject"] = f"KOMU Sports Data - {date.today()}"
msg["From"] = EMAIL_FROM
msg["To"] = EMAIL_TO
msg.set_content(
    f"Attached is this week's KOMU sports data export.\n\nFile: {XLSX_PATH}"
)

with open(XLSX_PATH, "rb") as f:
    msg.add_attachment(
        f.read(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=os.path.basename(XLSX_PATH),
    )

# Send through Gmail SMTP
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(EMAIL_FROM, EMAIL_PASSWORD)
    smtp.send_message(msg)

print("Email sent successfully.")