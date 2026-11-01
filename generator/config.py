"""Configuration shared by the DeductionDesk data generators."""

from __future__ import annotations

import os
import random
from pathlib import Path

from dotenv import load_dotenv
from faker import Faker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://localhost:5432/deductiondesk"
)
SEED = int(os.getenv("DEDUCTION_DESK_SEED", "20261101"))
DEDUCTION_COUNT = int(os.getenv("DEDUCTION_COUNT", "750"))

if not 500 <= DEDUCTION_COUNT <= 1000:
    raise ValueError("DEDUCTION_COUNT must be between 500 and 1000")

random.seed(SEED)
fake = Faker("en_US")
Faker.seed(SEED)

PRODUCTS = [
    {"sku": "SNK-CHD-12", "name": "Cheddar Crunch 12 oz", "unit_price": 3.89},
    {"sku": "SNK-BBQ-12", "name": "Smoky BBQ Crisps 12 oz", "unit_price": 3.89},
    {"sku": "BEV-LMN-08", "name": "Sparkling Lemon 8-pack", "unit_price": 6.49},
    {"sku": "BEV-BRY-08", "name": "Sparkling Berry 8-pack", "unit_price": 6.49},
    {"sku": "BRK-OAT-06", "name": "Maple Oat Bars 6-count", "unit_price": 4.79},
    {"sku": "PAN-SAL-16", "name": "Sea Salt Crackers 16 oz", "unit_price": 4.29},
    {"sku": "FRZ-PIZ-01", "name": "Four Cheese Flatbread", "unit_price": 7.99},
    {"sku": "HBA-SPR-01", "name": "Citrus Hand Spray", "unit_price": 5.59},
]

DEDUCTION_TYPE_WEIGHTS = {
    "shortage": 0.34,
    "promotional": 0.30,
    "pricing": 0.16,
    "compliance": 0.12,
    "damage": 0.08,
}
