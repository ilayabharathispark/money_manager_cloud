"""
categories.py — Category taxonomy and rule-based classification fallback.
Replicated for Money Manager Cloud.
"""

CATEGORIES = [
    "Food & Dining",
    "Groceries",
    "Transport & Fuel",
    "Shopping",
    "Bills & Utilities",
    "Entertainment",
    "Health & Medical",
    "Education",
    "Travel",
    "EMI & Loans",
    "Insurance",
    "ATM Withdrawal",
    "Transfer",
    "Income / Credit",
    "Other",
]

KEYWORD_RULES: list[tuple[list[str], str]] = [
    (["swiggy", "zomato", "food", "restaurant", "hotel", "cafe", "biryani", "pizza", "burger", "kfc", "mcdonalds", "dominos"], "Food & Dining"),
    (["grocery", "grocer", "bigbasket", "blinkit", "zepto", "dmart", "reliance fresh", "supermarket", "more store"], "Groceries"),
    (["ola", "uber", "rapido", "bus", "metro", "train", "irctc", "petrol", "fuel", "hp", "indane", "bharat petroleum", "iocl", "auto"], "Transport & Fuel"),
    (["amazon", "flipkart", "myntra", "ajio", "meesho", "nykaa", "shopping", "mall", "reliance retail", "croma", "vijay sales"], "Shopping"),
    (["electricity", "bescom", "tneb", "water board", "gas bill", "airtel", "jio", "vi ", "bsnl", "broadband", "internet", "mobile recharge", "recharge", "postpaid", "bill pay", "utility"], "Bills & Utilities"),
    (["netflix", "prime video", "hotstar", "sony liv", "zee5", "spotify", "bookmyshow", "pvr", "inox", "cinema", "theatre", "concert"], "Entertainment"),
    (["hospital", "clinic", "pharmacy", "medplus", "apollo", "netmeds", "1mg", "doctor", "medicine", "lab test", "diagnostic", "health"], "Health & Medical"),
    (["school", "college", "university", "fees", "tuition", "coaching", "udemy", "coursera", "unacademy", "byjus", "education"], "Education"),
    (["flight", "airline", "indigo", "air india", "spicejet", "hotel booking", "oyo", "makemytrip", "goibibo", "cleartrip", "travel"], "Travel"),
    (["emi", "loan", "lic", "insurance premium", "hdfc life", "bajaj allianz", "sbi life", "term plan", "policy"], "EMI & Loans"),
    (["atm", "cash withdrawal", "atm withdrawal"], "ATM Withdrawal"),
    (["neft", "imps", "upi transfer", "rtgs", "fund transfer", "sent to", "transfer to"], "Transfer"),
    (["salary", "credit", "received", "cashback", "refund", "reversal", "interest credited"], "Income / Credit"),
]


def classify_merchant(merchant: str, description: str = "") -> str:
    """Keyword-based fallback classifier."""
    text = f"{merchant} {description}".lower()
    for keywords, category in KEYWORD_RULES:
        if any(kw in text for kw in keywords):
            return category
    return "Other"


def validate_category(category: str) -> str:
    """Ensure a category string is one of our valid categories."""
    if category in CATEGORIES:
        return category
    return "Other"
