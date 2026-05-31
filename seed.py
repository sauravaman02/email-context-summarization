"""Seed the database with realistic CPA firm email conversation data.

Creates 3 firms, 9 accountants (with varied roles), 9 clients, and ~50
realistic tax-related email conversations covering scenarios like:
  - W-2/1099 processing
  - IRS notices and responses
  - Business tax filings
  - Foreign income and FBAR
  - Charitable contributions
  - First-time homebuyer deductions

Usage:
    python seed.py

All accounts use password: password123
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import async_session_factory, init_db
from app.models import Accountant, Client, Email, Firm
from app.services.auth_service import hash_password

COMMON_PASSWORD = "password123"

FIRMS = [
    {"name": "Anderson & Associates CPAs"},
    {"name": "Baker Tax Group"},
    {"name": "Clark Financial Advisors"},
]

ACCOUNTANTS_PER_FIRM = [
    [
        {"full_name": "Sarah Anderson", "email": "sarah@anderson-cpa.com", "role": "firm_admin"},
        {"full_name": "Mike Chen", "email": "mike@anderson-cpa.com", "role": "accountant"},
        {"full_name": "Lisa Rodriguez", "email": "lisa@anderson-cpa.com", "role": "accountant"},
    ],
    [
        {"full_name": "James Baker", "email": "james@bakertax.com", "role": "firm_admin"},
        {"full_name": "Emily Watson", "email": "emily@bakertax.com", "role": "accountant"},
        {"full_name": "David Kim", "email": "david@bakertax.com", "role": "accountant"},
    ],
    [
        {"full_name": "Robert Clark", "email": "robert@clarkfinancial.com", "role": "superuser"},
        {"full_name": "Jennifer Lopez", "email": "jennifer@clarkfinancial.com", "role": "firm_admin"},
        {"full_name": "Tom Singh", "email": "tom@clarkfinancial.com", "role": "accountant"},
    ],
]

CLIENTS_PER_FIRM = [
    [
        {"name": "Akshar Patel", "email": "akshar.patel@gmail.com"},
        {"name": "Maria Santos", "email": "maria.santos@outlook.com"},
        {"name": "John Williams", "email": "john.williams@yahoo.com"},
    ],
    [
        {"name": "Priya Sharma", "email": "priya.sharma@gmail.com"},
        {"name": "Carlos Mendez", "email": "carlos.mendez@hotmail.com"},
        {"name": "Susan O'Brien", "email": "susan.obrien@gmail.com"},
    ],
    [
        {"name": "Wei Zhang", "email": "wei.zhang@gmail.com"},
        {"name": "Ahmed Hassan", "email": "ahmed.hassan@outlook.com"},
        {"name": "Rachel Green", "email": "rachel.green@yahoo.com"},
    ],
]


def _email_threads() -> list[list[dict]]:
    """Return pre-written email conversation threads for seeding."""
    return [
        # ── Thread 1: Akshar Patel – W-2 and 1099-INT issues ─────────
        [
            {
                "sender_name": "Akshar Patel",
                "sender_email": "akshar.patel@gmail.com",
                "recipients": [{"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"}],
                "subject": "Tax Documents for 2025 Filing",
                "body": (
                    "Hi Sarah,\n\nI wanted to get started on my 2025 tax return. I've received "
                    "my W-2 from my employer (TechCorp Inc.) but I'm still waiting on my "
                    "1099-INT from First National Bank. Should I wait for it or can we start "
                    "with what I have?\n\nAlso, I had some freelance income this year — about "
                    "$12,000 from consulting work. Do I need to provide anything specific for "
                    "that?\n\nThanks,\nAkshar"
                ),
                "days_ago": 30,
            },
            {
                "sender_name": "Sarah Anderson",
                "sender_email": "sarah@anderson-cpa.com",
                "recipients": [{"name": "Akshar Patel", "email": "akshar.patel@gmail.com"}],
                "subject": "Re: Tax Documents for 2025 Filing",
                "body": (
                    "Hi Akshar,\n\nGreat to hear from you! Let's definitely get started. "
                    "Please go ahead and send over your W-2 whenever you're ready.\n\nFor the "
                    "1099-INT, the bank should have it out by January 31st. If you haven't "
                    "received it by mid-February, let me know and we'll follow up with them.\n\n"
                    "For the freelance income, you'll need to provide:\n"
                    "1. Total income received ($12,000 as you mentioned)\n"
                    "2. Any 1099-NEC forms from clients who paid you over $600\n"
                    "3. A list of business expenses (home office, equipment, software, etc.)\n\n"
                    "I'm looping in Mike who will help with the Schedule C for your freelance "
                    "work.\n\nBest,\nSarah"
                ),
                "days_ago": 29,
            },
            {
                "sender_name": "Mike Chen",
                "sender_email": "mike@anderson-cpa.com",
                "recipients": [
                    {"name": "Akshar Patel", "email": "akshar.patel@gmail.com"},
                    {"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"},
                ],
                "subject": "Re: Tax Documents for 2025 Filing",
                "body": (
                    "Hi Akshar,\n\nMike here — Sarah asked me to help with your Schedule C. "
                    "A few questions about your freelance work:\n\n"
                    "1. Did you use a dedicated home office? If so, what's the square footage?\n"
                    "2. Did you purchase any equipment or software for the consulting?\n"
                    "3. Any travel expenses related to the consulting gigs?\n"
                    "4. Did you make any estimated tax payments during 2025?\n\n"
                    "Having this info will help us maximize your deductions.\n\nThanks,\nMike"
                ),
                "days_ago": 28,
            },
            {
                "sender_name": "Akshar Patel",
                "sender_email": "akshar.patel@gmail.com",
                "recipients": [
                    {"name": "Mike Chen", "email": "mike@anderson-cpa.com"},
                    {"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"},
                ],
                "subject": "Re: Tax Documents for 2025 Filing",
                "body": (
                    "Hi Mike,\n\nHere are the answers:\n\n"
                    "1. Yes, I have a dedicated home office — 150 sq ft out of a 1,200 sq ft "
                    "apartment.\n"
                    "2. I bought a new laptop ($1,800) and Adobe Creative Suite subscription "
                    "($600/year).\n"
                    "3. I had two trips to client sites — total travel expenses around $2,400.\n"
                    "4. I made Q1 and Q2 estimated payments of $1,000 each but forgot Q3 and "
                    "Q4. Will I owe a penalty for that?\n\n"
                    "I've attached my W-2 as well. Still no 1099-INT from the bank.\n\n"
                    "Akshar"
                ),
                "days_ago": 25,
            },
            {
                "sender_name": "Mike Chen",
                "sender_email": "mike@anderson-cpa.com",
                "recipients": [{"name": "Akshar Patel", "email": "akshar.patel@gmail.com"}],
                "subject": "Re: Tax Documents for 2025 Filing — Estimated Tax Penalty",
                "body": (
                    "Hi Akshar,\n\nThanks for the detailed info. Regarding the missed estimated "
                    "payments — there may be a small underpayment penalty, but we can calculate "
                    "the exact amount using Form 2210. Given your W-2 withholding, it might be "
                    "minimal.\n\nI've started preparing your Schedule C with the deductions you "
                    "mentioned. Quick summary:\n"
                    "- Home office deduction (simplified): $750 (150 sq ft × $5)\n"
                    "- Equipment: $1,800 (Section 179)\n"
                    "- Software: $600\n"
                    "- Travel: $2,400\n"
                    "- Total deductions: ~$5,550\n\n"
                    "Your net freelance income would be around $6,450. We still need the "
                    "1099-INT to finalize everything.\n\nMike"
                ),
                "days_ago": 22,
            },
            {
                "sender_name": "Akshar Patel",
                "sender_email": "akshar.patel@gmail.com",
                "recipients": [
                    {"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"},
                    {"name": "Mike Chen", "email": "mike@anderson-cpa.com"},
                ],
                "subject": "1099-INT Received + Question about Crypto",
                "body": (
                    "Hi Sarah and Mike,\n\nGood news — I finally received my 1099-INT from "
                    "First National Bank. Interest income was $342.\n\nOne more thing I forgot "
                    "to mention — I sold some cryptocurrency in 2025. I sold 0.5 BTC that I "
                    "bought in 2023 for $15,000 and sold for $22,000. How does this affect my "
                    "return?\n\nSorry for the late addition!\n\nAkshar"
                ),
                "days_ago": 15,
            },
            {
                "sender_name": "Lisa Rodriguez",
                "sender_email": "lisa@anderson-cpa.com",
                "recipients": [
                    {"name": "Akshar Patel", "email": "akshar.patel@gmail.com"},
                    {"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"},
                ],
                "subject": "Re: 1099-INT Received + Question about Crypto",
                "body": (
                    "Hi Akshar,\n\nLisa here — Sarah asked me to handle the crypto portion. "
                    "The BTC sale is a long-term capital gain since you held it over a year:\n\n"
                    "- Proceeds: $22,000\n"
                    "- Cost basis: $15,000\n"
                    "- Capital gain: $7,000\n\n"
                    "This will be reported on Schedule D and Form 8949. The long-term rate "
                    "depends on your total taxable income — likely 15%.\n\n"
                    "Do you have records of the purchase date and price? An exchange statement "
                    "from Coinbase/Gemini would be perfect.\n\nLisa"
                ),
                "days_ago": 13,
            },
            {
                "sender_name": "Akshar Patel",
                "sender_email": "akshar.patel@gmail.com",
                "recipients": [{"name": "Lisa Rodriguez", "email": "lisa@anderson-cpa.com"}],
                "subject": "Re: 1099-INT Received + Question about Crypto",
                "body": (
                    "Hi Lisa,\n\nYes, I have my Coinbase statement. I'll download and send it "
                    "over today. The purchase was on March 15, 2023 and the sale was on "
                    "August 20, 2025.\n\nThanks for explaining the tax treatment!\n\nAkshar"
                ),
                "days_ago": 12,
            },
        ],
        # ── Thread 2: Maria Santos – Business tax return ──────────────
        [
            {
                "sender_name": "Maria Santos",
                "sender_email": "maria.santos@outlook.com",
                "recipients": [{"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"}],
                "subject": "Small Business Tax Filing — Santos Bakery LLC",
                "body": (
                    "Hello Sarah,\n\nI need help filing the tax return for my bakery. This was "
                    "our first full year of operation. Revenue was about $180,000 and I'm not "
                    "sure what expenses are deductible.\n\nI have receipts for ingredients, "
                    "equipment, rent, and employee wages. How should I organize this?\n\n"
                    "Best,\nMaria Santos"
                ),
                "days_ago": 28,
            },
            {
                "sender_name": "Sarah Anderson",
                "sender_email": "sarah@anderson-cpa.com",
                "recipients": [{"name": "Maria Santos", "email": "maria.santos@outlook.com"}],
                "subject": "Re: Small Business Tax Filing — Santos Bakery LLC",
                "body": (
                    "Hi Maria,\n\nCongratulations on your first full year! I'd recommend "
                    "organizing your expenses into these categories:\n\n"
                    "1. Cost of Goods Sold (ingredients, packaging)\n"
                    "2. Rent and utilities\n"
                    "3. Employee wages and payroll taxes\n"
                    "4. Equipment purchases (may qualify for Section 179)\n"
                    "5. Insurance\n"
                    "6. Marketing and advertising\n\n"
                    "Can you provide your QuickBooks login or a P&L statement? That would "
                    "make this much smoother.\n\nSarah"
                ),
                "days_ago": 27,
            },
            {
                "sender_name": "Maria Santos",
                "sender_email": "maria.santos@outlook.com",
                "recipients": [{"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"}],
                "subject": "Re: Small Business Tax Filing — Santos Bakery LLC",
                "body": (
                    "Hi Sarah,\n\nI don't use QuickBooks yet — I've been tracking everything "
                    "in Excel. I'll send you the spreadsheet. Here's a rough breakdown:\n\n"
                    "- Ingredients: $52,000\n"
                    "- Rent: $24,000\n"
                    "- Employee wages (2 part-time): $36,000\n"
                    "- Equipment (commercial oven): $8,500\n"
                    "- Insurance: $3,600\n"
                    "- Utilities: $4,800\n\n"
                    "Total expenses around $128,900. Does that seem right?\n\nMaria"
                ),
                "days_ago": 25,
            },
            {
                "sender_name": "Mike Chen",
                "sender_email": "mike@anderson-cpa.com",
                "recipients": [
                    {"name": "Maria Santos", "email": "maria.santos@outlook.com"},
                    {"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"},
                ],
                "subject": "Re: Small Business Tax Filing — Action Items",
                "body": (
                    "Hi Maria,\n\nSarah asked me to review your numbers. A few things:\n\n"
                    "1. The commercial oven ($8,500) can be fully deducted this year under "
                    "Section 179 — great for reducing your tax bill.\n"
                    "2. Did you pay yourself a salary or take owner draws? This matters for "
                    "self-employment tax calculation.\n"
                    "3. We need your EIN and the LLC's formation documents.\n"
                    "4. I'd strongly recommend setting up QuickBooks for 2026 — it will save "
                    "you significant time.\n\n"
                    "Your estimated net income is ~$51,100, which means roughly $7,200 in "
                    "self-employment tax.\n\nMike"
                ),
                "days_ago": 20,
            },
            {
                "sender_name": "Maria Santos",
                "sender_email": "maria.santos@outlook.com",
                "recipients": [{"name": "Mike Chen", "email": "mike@anderson-cpa.com"}],
                "subject": "Re: Small Business Tax Filing — Action Items",
                "body": (
                    "Hi Mike,\n\nI took owner draws throughout the year, no formal salary. "
                    "Total draws were about $40,000.\n\nI'll send the EIN letter and LLC "
                    "docs tomorrow. And yes, I'll definitely set up QuickBooks for next "
                    "year!\n\nMaria"
                ),
                "days_ago": 18,
            },
        ],
        # ── Thread 3: John Williams – IRS notice ─────────────────────
        [
            {
                "sender_name": "John Williams",
                "sender_email": "john.williams@yahoo.com",
                "recipients": [{"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"}],
                "subject": "URGENT: IRS Notice CP2000 — Unreported Income",
                "body": (
                    "Sarah,\n\nI just received an IRS notice (CP2000) saying I have unreported "
                    "income of $8,400 from 2024. They're saying I owe $2,100 plus penalties. "
                    "I think this is from a stock sale I forgot to report.\n\n"
                    "The response deadline is in 30 days. What should I do?\n\n"
                    "Very worried,\nJohn"
                ),
                "days_ago": 20,
            },
            {
                "sender_name": "Sarah Anderson",
                "sender_email": "sarah@anderson-cpa.com",
                "recipients": [{"name": "John Williams", "email": "john.williams@yahoo.com"}],
                "subject": "Re: URGENT: IRS Notice CP2000 — Don't Panic",
                "body": (
                    "John,\n\nDon't panic — CP2000 notices are very common and usually "
                    "straightforward to resolve. Here's what I need from you:\n\n"
                    "1. A copy of the CP2000 notice (scan or photo)\n"
                    "2. Your 1099-B from the brokerage for the stock sale\n"
                    "3. Proof of your cost basis (purchase price) for the stocks\n\n"
                    "Important: the IRS is reporting the full sale PROCEEDS as income. If you "
                    "had a cost basis, your actual gain could be much less than $8,400.\n\n"
                    "We have 30 days to respond — I'll draft the response letter once I see "
                    "the documents.\n\nSarah"
                ),
                "days_ago": 19,
            },
            {
                "sender_name": "John Williams",
                "sender_email": "john.williams@yahoo.com",
                "recipients": [{"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"}],
                "subject": "Re: URGENT: IRS Notice CP2000 — Documents",
                "body": (
                    "Sarah,\n\nI found everything. The 1099-B shows:\n"
                    "- Sold 100 shares of AAPL for $18,400\n"
                    "- I bought them in 2020 for $10,000\n"
                    "- So the actual capital gain is $8,400\n\n"
                    "But it's long-term since I held for over a year. Does that help reduce "
                    "the tax owed?\n\nJohn"
                ),
                "days_ago": 17,
            },
            {
                "sender_name": "Lisa Rodriguez",
                "sender_email": "lisa@anderson-cpa.com",
                "recipients": [
                    {"name": "John Williams", "email": "john.williams@yahoo.com"},
                    {"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"},
                ],
                "subject": "Re: URGENT: IRS Notice CP2000 — Good News",
                "body": (
                    "Hi John,\n\nLisa here — I've reviewed the CP2000 notice and your 1099-B. "
                    "Good news:\n\n"
                    "1. The IRS reported $18,400 as income (gross proceeds), but your actual "
                    "gain is $8,400 after cost basis.\n"
                    "2. As a long-term gain, the tax rate is 15% instead of your ordinary "
                    "rate — so the tax owed is ~$1,260, NOT $2,100.\n"
                    "3. We'll prepare a response with the cost basis documentation to get the "
                    "amount reduced.\n\n"
                    "I'll have the response letter ready for your review by Friday. We'll "
                    "request penalty abatement since this was a good-faith omission.\n\nLisa"
                ),
                "days_ago": 14,
            },
        ],
        # ── Thread 4: Priya Sharma (Firm 2) – Multiple income sources ─
        [
            {
                "sender_name": "Priya Sharma",
                "sender_email": "priya.sharma@gmail.com",
                "recipients": [{"name": "Emily Watson", "email": "emily@bakertax.com"}],
                "subject": "Complex Tax Situation — Multiple Income Sources",
                "body": (
                    "Hi Emily,\n\nMy tax situation is a bit complicated this year:\n\n"
                    "1. Full-time job at MegaCorp — W-2 income $95,000\n"
                    "2. Rental property income — $18,000 gross, with $12,000 in expenses\n"
                    "3. Dividend income from investments — $3,200\n"
                    "4. I also started a side business selling handmade jewelry on Etsy — "
                    "revenue was $8,500\n\n"
                    "What documents do I need to gather?\n\nPriya"
                ),
                "days_ago": 26,
            },
            {
                "sender_name": "Emily Watson",
                "sender_email": "emily@bakertax.com",
                "recipients": [{"name": "Priya Sharma", "email": "priya.sharma@gmail.com"}],
                "subject": "Re: Complex Tax Situation — Document Checklist",
                "body": (
                    "Hi Priya,\n\nThat's quite the portfolio! Here's your document checklist:\n\n"
                    "Employment:\n- W-2 from MegaCorp\n\n"
                    "Rental Property:\n- Rental income records\n- Mortgage interest (Form 1098)\n"
                    "- Property tax bills\n- Repair/maintenance receipts\n"
                    "- Depreciation schedule (I'll calculate if this is year 1)\n\n"
                    "Investments:\n- 1099-DIV for dividends\n- Any 1099-B for stock sales\n\n"
                    "Etsy Business:\n- 1099-K from Etsy (if over $600)\n"
                    "- Materials/supply receipts\n- Shipping costs\n- PayPal/payment records\n\n"
                    "Let me know when you have these ready!\n\nEmily"
                ),
                "days_ago": 25,
            },
            {
                "sender_name": "David Kim",
                "sender_email": "david@bakertax.com",
                "recipients": [
                    {"name": "Priya Sharma", "email": "priya.sharma@gmail.com"},
                    {"name": "Emily Watson", "email": "emily@bakertax.com"},
                ],
                "subject": "Re: Complex Tax Situation — Rental Property Questions",
                "body": (
                    "Hi Priya,\n\nDavid here — Emily asked me to handle the rental property "
                    "portion. A few questions:\n\n"
                    "1. When did you purchase the property and for how much?\n"
                    "2. Is it a single-family home, condo, or multi-unit?\n"
                    "3. How many days was it rented out in 2025?\n"
                    "4. Did you use a property management company?\n"
                    "5. Any major repairs or improvements this year?\n\n"
                    "The answers will help me determine the depreciation deduction and ensure "
                    "we're capturing all allowable expenses.\n\nDavid"
                ),
                "days_ago": 23,
            },
            {
                "sender_name": "Priya Sharma",
                "sender_email": "priya.sharma@gmail.com",
                "recipients": [
                    {"name": "David Kim", "email": "david@bakertax.com"},
                    {"name": "Emily Watson", "email": "emily@bakertax.com"},
                ],
                "subject": "Re: Complex Tax Situation — Rental Answers",
                "body": (
                    "Hi David,\n\n"
                    "1. Purchased in June 2022 for $320,000\n"
                    "2. It's a single-family home\n"
                    "3. Rented the full 12 months\n"
                    "4. Yes — I use GreenTree Property Management (they take 8% of rent)\n"
                    "5. I replaced the HVAC system for $6,200 — is that deductible?\n\n"
                    "Priya"
                ),
                "days_ago": 21,
            },
            {
                "sender_name": "David Kim",
                "sender_email": "david@bakertax.com",
                "recipients": [{"name": "Priya Sharma", "email": "priya.sharma@gmail.com"}],
                "subject": "Re: Complex Tax Situation — HVAC Deduction",
                "body": (
                    "Hi Priya,\n\nGreat info. Regarding the HVAC:\n\n"
                    "The $6,200 HVAC replacement is considered a capital improvement, not a "
                    "repair. This means it gets depreciated over 27.5 years rather than "
                    "deducted in full this year. That's about $225/year in depreciation.\n\n"
                    "For the house itself, the building portion (excluding land, typically 80% "
                    "of purchase price = ~$256,000) is depreciated over 27.5 years = ~$9,309/"
                    "year. Since you've owned it since 2022, you should already have this on "
                    "prior returns.\n\n"
                    "I'll pull up your 2024 return to ensure continuity.\n\nDavid"
                ),
                "days_ago": 18,
            },
        ],
        # ── Thread 5: Carlos Mendez (Firm 2) – Late filing extension ──
        [
            {
                "sender_name": "Carlos Mendez",
                "sender_email": "carlos.mendez@hotmail.com",
                "recipients": [{"name": "James Baker", "email": "james@bakertax.com"}],
                "subject": "Need to File Extension — Not Ready Yet",
                "body": (
                    "James,\n\nI'm not going to be ready to file by April 15th. I'm still "
                    "waiting on a K-1 from a partnership I'm invested in. Can you file an "
                    "extension for me?\n\n"
                    "Also, do I need to pay anything with the extension?\n\nCarlos"
                ),
                "days_ago": 25,
            },
            {
                "sender_name": "James Baker",
                "sender_email": "james@bakertax.com",
                "recipients": [{"name": "Carlos Mendez", "email": "carlos.mendez@hotmail.com"}],
                "subject": "Re: Need to File Extension",
                "body": (
                    "Carlos,\n\nAbsolutely — I'll file Form 4868 to extend your deadline to "
                    "October 15th.\n\n"
                    "Important: the extension gives you more time to FILE, but not more time "
                    "to PAY. If you expect to owe taxes, you should make an estimated payment "
                    "by April 15th to avoid interest and penalties.\n\n"
                    "Based on your 2024 return, I'd recommend paying at least $3,000 as an "
                    "estimated payment. Want me to set that up for you through EFTPS?\n\nJames"
                ),
                "days_ago": 24,
            },
            {
                "sender_name": "Carlos Mendez",
                "sender_email": "carlos.mendez@hotmail.com",
                "recipients": [{"name": "James Baker", "email": "james@bakertax.com"}],
                "subject": "Re: Need to File Extension — Go ahead",
                "body": (
                    "James,\n\nYes, please file the extension and set up the $3,000 payment. "
                    "Use the bank account on file.\n\nI should have the K-1 by end of May. "
                    "I'll send it over as soon as I get it.\n\nThanks,\nCarlos"
                ),
                "days_ago": 22,
            },
        ],
        # ── Thread 6: Susan O'Brien (Firm 2) – Charitable donations ──
        [
            {
                "sender_name": "Susan O'Brien",
                "sender_email": "susan.obrien@gmail.com",
                "recipients": [{"name": "Emily Watson", "email": "emily@bakertax.com"}],
                "subject": "Charitable Contributions — Am I Over the Limit?",
                "body": (
                    "Hi Emily,\n\nI made significant charitable contributions in 2025:\n\n"
                    "- $15,000 cash to St. Mary's Church\n"
                    "- $8,000 to Red Cross\n"
                    "- Donated a car valued at $12,000 to Goodwill\n"
                    "- $5,000 to my alma mater's scholarship fund\n\n"
                    "My AGI is about $120,000. Am I hitting any limits?\n\nSusan"
                ),
                "days_ago": 22,
            },
            {
                "sender_name": "Emily Watson",
                "sender_email": "emily@bakertax.com",
                "recipients": [{"name": "Susan O'Brien", "email": "susan.obrien@gmail.com"}],
                "subject": "Re: Charitable Contributions — Analysis",
                "body": (
                    "Hi Susan,\n\nGreat question. Here's the breakdown:\n\n"
                    "Cash donations ($15,000 + $8,000 + $5,000 = $28,000): limited to 60% of "
                    "AGI = $72,000. You're well under this limit.\n\n"
                    "Car donation ($12,000): Non-cash contributions over $500 require Form "
                    "8283. For a car over $5,000, you'll need a written appraisal AND the "
                    "charity's acknowledgment letter showing what they did with the car.\n\n"
                    "Total deductions: $40,000. This exceeds the standard deduction ($14,600), "
                    "so you should definitely itemize.\n\n"
                    "I'll need the donation receipts for all contributions over $250.\n\nEmily"
                ),
                "days_ago": 20,
            },
        ],
        # ── Thread 7: Wei Zhang (Firm 3) – Foreign income ────────────
        [
            {
                "sender_name": "Wei Zhang",
                "sender_email": "wei.zhang@gmail.com",
                "recipients": [{"name": "Tom Singh", "email": "tom@clarkfinancial.com"}],
                "subject": "Foreign Income and FBAR Filing",
                "body": (
                    "Hi Tom,\n\nI have income from China that I need to report:\n\n"
                    "1. Rental income from a property in Shanghai: ¥180,000 (~$25,000)\n"
                    "2. Bank interest from ICBC: ¥8,500 (~$1,180)\n"
                    "3. My Chinese bank accounts had a combined maximum of ¥720,000 (~$100,000) "
                    "at one point during the year\n\n"
                    "I know I need to file FBAR. Are there other forms?\n\nWei"
                ),
                "days_ago": 24,
            },
            {
                "sender_name": "Tom Singh",
                "sender_email": "tom@clarkfinancial.com",
                "recipients": [
                    {"name": "Wei Zhang", "email": "wei.zhang@gmail.com"},
                    {"name": "Jennifer Lopez", "email": "jennifer@clarkfinancial.com"},
                ],
                "subject": "Re: Foreign Income and FBAR Filing",
                "body": (
                    "Hi Wei,\n\nYes, you have several filing obligations:\n\n"
                    "1. FBAR (FinCEN 114): Required since your foreign accounts exceeded "
                    "$10,000 at any point. Due April 15 with auto-extension to October.\n\n"
                    "2. Form 8938 (FATCA): Required if foreign assets exceed $50,000 (end of "
                    "year) or $75,000 (during year) for single filers.\n\n"
                    "3. Schedule E for the rental income (converted to USD).\n\n"
                    "4. Foreign Tax Credit (Form 1116): If you paid taxes to China on this "
                    "income, we can claim a credit to avoid double taxation.\n\n"
                    "Did you pay Chinese taxes on the rental income? If so, how much?\n\n"
                    "Copying Jennifer who oversees our international tax filings.\n\nTom"
                ),
                "days_ago": 22,
            },
            {
                "sender_name": "Wei Zhang",
                "sender_email": "wei.zhang@gmail.com",
                "recipients": [
                    {"name": "Tom Singh", "email": "tom@clarkfinancial.com"},
                    {"name": "Jennifer Lopez", "email": "jennifer@clarkfinancial.com"},
                ],
                "subject": "Re: Foreign Income and FBAR Filing — Chinese Taxes",
                "body": (
                    "Hi Tom and Jennifer,\n\nYes, I paid Chinese taxes:\n"
                    "- Rental income tax: ¥36,000 (~$5,000)\n"
                    "- Interest withholding: ¥1,700 (~$236)\n\n"
                    "I have the Chinese tax receipts. Should I get them translated?\n\nWei"
                ),
                "days_ago": 20,
            },
            {
                "sender_name": "Jennifer Lopez",
                "sender_email": "jennifer@clarkfinancial.com",
                "recipients": [
                    {"name": "Wei Zhang", "email": "wei.zhang@gmail.com"},
                    {"name": "Tom Singh", "email": "tom@clarkfinancial.com"},
                ],
                "subject": "Re: Foreign Income and FBAR Filing — Next Steps",
                "body": (
                    "Hi Wei,\n\nJennifer here. Yes, please get the tax receipts translated — "
                    "a certified translation is ideal but not strictly required by the IRS. A "
                    "clear English summary would work.\n\n"
                    "The Foreign Tax Credit of ~$5,236 will significantly offset your US tax "
                    "on this income. In many cases, it results in little to no additional US "
                    "tax on the foreign income.\n\n"
                    "Action items:\n"
                    "1. Send translated tax receipts\n"
                    "2. Provide all bank account details (name, account number, max balance) "
                    "for FBAR\n"
                    "3. Send the rental agreement showing income terms\n\n"
                    "We'll handle FBAR, Form 8938, and Form 1116 for you.\n\nJennifer"
                ),
                "days_ago": 18,
            },
        ],
        # ── Thread 8: Ahmed Hassan (Firm 3) – Medical expenses ───────
        [
            {
                "sender_name": "Ahmed Hassan",
                "sender_email": "ahmed.hassan@outlook.com",
                "recipients": [{"name": "Tom Singh", "email": "tom@clarkfinancial.com"}],
                "subject": "Major Medical Expenses in 2025",
                "body": (
                    "Tom,\n\nI had a rough year health-wise. My medical expenses were:\n\n"
                    "- Surgery (out-of-pocket after insurance): $14,000\n"
                    "- Prescription medications: $3,200\n"
                    "- Physical therapy: $4,800\n"
                    "- Health insurance premiums (not from employer): $9,600\n\n"
                    "My AGI is about $85,000. Can I deduct any of this?\n\nAhmed"
                ),
                "days_ago": 18,
            },
            {
                "sender_name": "Tom Singh",
                "sender_email": "tom@clarkfinancial.com",
                "recipients": [{"name": "Ahmed Hassan", "email": "ahmed.hassan@outlook.com"}],
                "subject": "Re: Major Medical Expenses — Good News",
                "body": (
                    "Ahmed,\n\nSorry to hear about the health challenges. The good news is "
                    "you can deduct a significant portion:\n\n"
                    "Total medical expenses: $31,600\n"
                    "7.5% of AGI threshold: $6,375\n"
                    "Deductible amount: $25,225\n\n"
                    "This alone makes itemizing worthwhile. Combined with any other deductions "
                    "(state taxes, mortgage interest, etc.), you'll save substantially.\n\n"
                    "Please gather:\n"
                    "- Explanation of Benefits (EOB) statements from insurance\n"
                    "- Pharmacy receipts or printout from your pharmacy\n"
                    "- Receipts from physical therapy\n"
                    "- Form 1095-A/B/C for insurance\n\nTom"
                ),
                "days_ago": 16,
            },
        ],
        # ── Thread 9: Rachel Green (Firm 3) – First-time homebuyer ───
        [
            {
                "sender_name": "Rachel Green",
                "sender_email": "rachel.green@yahoo.com",
                "recipients": [{"name": "Jennifer Lopez", "email": "jennifer@clarkfinancial.com"}],
                "subject": "Bought My First Home! Tax Implications?",
                "body": (
                    "Hi Jennifer,\n\nI closed on my first home in July 2025! Purchase price "
                    "was $380,000 with a $76,000 down payment.\n\n"
                    "Questions:\n"
                    "1. What can I deduct related to the home purchase?\n"
                    "2. I paid $4,200 in points to lower my mortgage rate — is that deductible?\n"
                    "3. My property taxes for 2025 were $3,800\n"
                    "4. I also have $1,200 in PMI — is that still deductible?\n\n"
                    "Excited but also nervous about the tax changes!\n\nRachel"
                ),
                "days_ago": 14,
            },
            {
                "sender_name": "Jennifer Lopez",
                "sender_email": "jennifer@clarkfinancial.com",
                "recipients": [{"name": "Rachel Green", "email": "rachel.green@yahoo.com"}],
                "subject": "Re: Bought My First Home! — Tax Benefits",
                "body": (
                    "Congratulations Rachel!\n\nHere's your first-year homeowner tax breakdown:\n\n"
                    "1. Mortgage interest: Deductible on Schedule A. Your lender will send "
                    "Form 1098. For a $304,000 mortgage, expect ~$12,000-15,000 in interest "
                    "for the first partial year.\n\n"
                    "2. Points ($4,200): Fully deductible in the year of purchase since this is "
                    "your primary residence and you meet all IRS requirements.\n\n"
                    "3. Property taxes ($3,800): Deductible, but combined with state income "
                    "tax, capped at $10,000 (SALT limitation).\n\n"
                    "4. PMI ($1,200): Currently deductible for AGI under $100,000.\n\n"
                    "Total potential itemized deductions from the home: ~$21,200-24,200. "
                    "Definitely worth itemizing!\n\n"
                    "Send me your HUD-1/Closing Disclosure and Form 1098 when available.\n\n"
                    "Jennifer"
                ),
                "days_ago": 12,
            },
            {
                "sender_name": "Rachel Green",
                "sender_email": "rachel.green@yahoo.com",
                "recipients": [{"name": "Jennifer Lopez", "email": "jennifer@clarkfinancial.com"}],
                "subject": "Re: Bought My First Home! — More Questions",
                "body": (
                    "Thanks Jennifer! That's really helpful.\n\n"
                    "Two more questions:\n"
                    "1. I withdrew $10,000 from my Roth IRA for the down payment as a "
                    "first-time homebuyer. Is there a penalty?\n"
                    "2. I also paid $2,800 in moving expenses to relocate for a new job. "
                    "Can I deduct that?\n\nRachel"
                ),
                "days_ago": 10,
            },
            {
                "sender_name": "Jennifer Lopez",
                "sender_email": "jennifer@clarkfinancial.com",
                "recipients": [{"name": "Rachel Green", "email": "rachel.green@yahoo.com"}],
                "subject": "Re: Bought My First Home! — Roth IRA & Moving",
                "body": (
                    "Great questions Rachel:\n\n"
                    "1. Roth IRA withdrawal: You can withdraw CONTRIBUTIONS tax-free anytime. "
                    "For EARNINGS, the first-time homebuyer exception allows up to $10,000 "
                    "penalty-free, but earnings may still be taxable if the account is under "
                    "5 years old. When did you open the Roth?\n\n"
                    "2. Moving expenses: Unfortunately, the moving expense deduction was "
                    "suspended for most taxpayers from 2018-2025 under the TCJA. It's only "
                    "available for active-duty military. So no deduction for the $2,800.\n\n"
                    "Let me know about the Roth timeline and I'll calculate the tax "
                    "impact.\n\nJennifer"
                ),
                "days_ago": 8,
            },
        ],
    ]


async def seed() -> None:
    await init_db()

    threads = _email_threads()
    thread_idx = 0

    async with async_session_factory() as session:
        for firm_idx, firm_data in enumerate(FIRMS):
            firm = Firm(name=firm_data["name"])
            session.add(firm)
            await session.flush()

            for acc_data in ACCOUNTANTS_PER_FIRM[firm_idx]:
                accountant = Accountant(
                    firm_id=firm.id,
                    email=acc_data["email"],
                    full_name=acc_data["full_name"],
                    hashed_password=hash_password(COMMON_PASSWORD),
                    role=acc_data["role"],
                )
                session.add(accountant)

            for client_data in CLIENTS_PER_FIRM[firm_idx]:
                client = Client(
                    firm_id=firm.id,
                    name=client_data["name"],
                    email=client_data["email"],
                )
                session.add(client)
                await session.flush()

                if thread_idx < len(threads):
                    now = datetime.now(timezone.utc)
                    for email_data in threads[thread_idx]:
                        sent_at = now - timedelta(days=email_data["days_ago"])
                        email = Email(
                            client_id=client.id,
                            sender_email=email_data["sender_email"],
                            sender_name=email_data["sender_name"],
                            recipients=email_data["recipients"],
                            subject=email_data["subject"],
                            body=email_data["body"],
                            sent_at=sent_at,
                        )
                        session.add(email)
                    thread_idx += 1

        await session.commit()

    print("Database seeded successfully!")
    print(f"  Firms: {len(FIRMS)}")
    print(f"  Accountants: {sum(len(a) for a in ACCOUNTANTS_PER_FIRM)}")
    print(f"  Clients: {sum(len(c) for c in CLIENTS_PER_FIRM)}")
    print(f"  Email threads: {thread_idx}")
    print(f"\nLogin credentials (all accounts): password = '{COMMON_PASSWORD}'")
    print("Superuser: robert@clarkfinancial.com")
    print("Firm admins: sarah@anderson-cpa.com, james@bakertax.com, jennifer@clarkfinancial.com")


if __name__ == "__main__":
    asyncio.run(seed())
