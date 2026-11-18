import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("phone_agent.knowledge_base")
KNOWLEDGE_PATH = Path(__file__).parent / "company_knowledge.json"

class CompanyKnowledgeBase:
    """Manages company business knowledge, FAQ lookups, and department extensions."""

    def __init__(self, file_path: Path = KNOWLEDGE_PATH):
        self.file_path = file_path
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self):
        if self.file_path.exists():
            try:
                self.data = json.loads(self.file_path.read_text(encoding="utf-8"))
                logger.info(f"Loaded knowledge base from {self.file_path}")
            except Exception as e:
                logger.error(f"Failed to read knowledge base: {e}")
                self.data = {}
        else:
            self.data = {}

    def search_faq(self, query: str) -> str:
        """Finds the most relevant FAQ answer or company info based on keywords."""
        q = query.lower()
        overview = self.data.get("company_overview", {})
        
        # Check overview fields
        if any(w in q for w in ["hour", "open", "close", "time", "schedule"]):
            return f"Our business hours are {overview.get('hours', '8:30 AM - 5:30 PM EST')}."
        if any(w in q for w in ["address", "where", "location", "office", "street"]):
            return f"Our office is located at {overview.get('address', '123 Main Street, Suite 400')}."
        if any(w in q for w in ["phone", "call", "number"]):
            return f"Our main phone number is {overview.get('phone', '555-123-4567')}."
        if any(w in q for w in ["email", "mail", "contact"]):
            return f"You can reach our team by email at {overview.get('email', 'support@example.com')}."

        # Check FAQ items
        for item in self.data.get("faq", []):
            if any(term in q for term in item.get("topic", "").split("_")):
                return item.get("answer", "")
            if any(word in q for word in item.get("question", "").lower().split() if len(word) > 4):
                return item.get("answer", "")

        return (
            f"{overview.get('name', 'Our company')} provides {overview.get('description', 'business services')}. "
            f"Hours: {overview.get('hours', 'Mon-Fri 8:30-5:30')}. Address: {overview.get('address', 'Main Office')}."
        )

    def get_department_extension(self, department_name: str) -> str:
        """Finds extension for a department."""
        dept_lower = department_name.lower()
        for d in self.data.get("departments", []):
            if d.get("name", "").lower() in dept_lower or dept_lower in d.get("name", "").lower():
                return d.get("extension", "1000")
        return "1000"

knowledge_base = CompanyKnowledgeBase()
