"""
Mock flight data — realistic fake flights for demo & testing.

Generates fake SearchFlight response data matching the AGT API format
so that `format_flight_results` can consume it without changes.
Only used when the real AGT API returns no results or fails.
"""

from __future__ import annotations

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Realistic flight data
# ---------------------------------------------------------------------------

# Airlines: code, name, flight number range
AIRLINES = {
    "VN": {"name": "Vietnam Airlines", "range": (100, 999)},
    "VJ": {"name": "VietJet Air",    "range": (300, 799)},
    "QH": {"name": "Bamboo Airways",  "range": (200, 499)},
    "BL": {"name": "Pacific Airlines", "range": (100, 399)},
    "VU": {"name": "Vietravel Airlines", "range": (50, 199)},
}

# Standard routes: origin, dest, flight time (minutes), departures
ROUTES = {
    ("SGN", "HAN"): {
        "duration": 120,
        "flights": [
            {"time": "06:15", "airline": "VN", "price": 1850000},
            {"time": "07:30", "airline": "VJ", "price": 1250000},
            {"time": "08:45", "airline": "QH", "price": 1550000},
            {"time": "09:20", "airline": "VN", "price": 1950000},
            {"time": "10:00", "airline": "BL", "price": 1150000},
            {"time": "12:30", "airline": "VJ", "price": 1350000},
            {"time": "14:00", "airline": "VN", "price": 1750000},
            {"time": "15:45", "airline": "QH", "price": 1450000},
            {"time": "17:20", "airline": "VU", "price": 1650000},
            {"time": "18:00", "airline": "VJ", "price": 1290000},
            {"time": "19:30", "airline": "VN", "price": 2100000},
            {"time": "21:00", "airline": "BL", "price": 1090000},
        ],
    },
    ("HAN", "SGN"): {
        "duration": 125,
        "flights": [
            {"time": "05:50", "airline": "VN", "price": 1950000},
            {"time": "06:30", "airline": "VJ", "price": 1350000},
            {"time": "08:00", "airline": "QH", "price": 1650000},
            {"time": "09:15", "airline": "BL", "price": 1190000},
            {"time": "10:30", "airline": "VN", "price": 2050000},
            {"time": "12:00", "airline": "VJ", "price": 1290000},
            {"time": "13:45", "airline": "VU", "price": 1590000},
            {"time": "15:20", "airline": "QH", "price": 1550000},
            {"time": "17:00", "airline": "VN", "price": 1890000},
            {"time": "18:30", "airline": "VJ", "price": 1250000},
            {"time": "20:00", "airline": "BL", "price": 1050000},
            {"time": "21:30", "airline": "VN", "price": 2350000},
        ],
    },
    ("SGN", "DAD"): {
        "duration": 65,
        "flights": [
            {"time": "06:00", "airline": "VN", "price": 1250000},
            {"time": "07:20", "airline": "VJ", "price": 890000},
            {"time": "09:00", "airline": "QH", "price": 1100000},
            {"time": "10:45", "airline": "BL", "price": 790000},
            {"time": "13:00", "airline": "VJ", "price": 950000},
            {"time": "15:30", "airline": "VN", "price": 1350000},
            {"time": "17:45", "airline": "QH", "price": 1150000},
            {"time": "19:00", "airline": "VU", "price": 1050000},
            {"time": "20:30", "airline": "VJ", "price": 890000},
        ],
    },
    ("DAD", "SGN"): {
        "duration": 65,
        "flights": [
            {"time": "06:30", "airline": "VJ", "price": 890000},
            {"time": "08:00", "airline": "VN", "price": 1290000},
            {"time": "09:40", "airline": "BL", "price": 790000},
            {"time": "11:20", "airline": "QH", "price": 1050000},
            {"time": "14:00", "airline": "VJ", "price": 950000},
            {"time": "16:15", "airline": "VN", "price": 1350000},
            {"time": "18:00", "airline": "QH", "price": 1100000},
            {"time": "20:00", "airline": "VU", "price": 990000},
        ],
    },
    ("SGN", "PQC"): {
        "duration": 55,
        "flights": [
            {"time": "07:00", "airline": "VN", "price": 1500000},
            {"time": "09:30", "airline": "VJ", "price": 990000},
            {"time": "12:00", "airline": "QH", "price": 1250000},
            {"time": "14:30", "airline": "BL", "price": 890000},
            {"time": "16:00", "airline": "VJ", "price": 1050000},
            {"time": "19:00", "airline": "VN", "price": 1650000},
        ],
    },
    ("PQC", "SGN"): {
        "duration": 55,
        "flights": [
            {"time": "06:00", "airline": "VJ", "price": 890000},
            {"time": "08:30", "airline": "VN", "price": 1500000},
            {"time": "11:00", "airline": "QH", "price": 1200000},
            {"time": "13:30", "airline": "BL", "price": 790000},
            {"time": "15:00", "airline": "VJ", "price": 990000},
            {"time": "18:00", "airline": "VN", "price": 1690000},
        ],
    },
    ("SGN", "CXR"): {
        "duration": 60,
        "flights": [
            {"time": "06:45", "airline": "VJ", "price": 690000},
            {"time": "08:30", "airline": "VN", "price": 1100000},
            {"time": "10:00", "airline": "QH", "price": 950000},
            {"time": "13:00", "airline": "VJ", "price": 790000},
            {"time": "15:30", "airline": "VN", "price": 1250000},
            {"time": "18:00", "airline": "VU", "price": 990000},
        ],
    },
    ("CXR", "SGN"): {
        "duration": 60,
        "flights": [
            {"time": "07:30", "airline": "VJ", "price": 690000},
            {"time": "09:15", "airline": "VN", "price": 1150000},
            {"time": "11:00", "airline": "QH", "price": 950000},
            {"time": "14:00", "airline": "VJ", "price": 790000},
            {"time": "16:30", "airline": "VN", "price": 1250000},
            {"time": "19:00", "airline": "VU", "price": 990000},
        ],
    },
    ("HAN", "DAD"): {
        "duration": 80,
        "flights": [
            {"time": "06:00", "airline": "VN", "price": 950000},
            {"time": "08:30", "airline": "VJ", "price": 690000},
            {"time": "10:00", "airline": "QH", "price": 850000},
            {"time": "13:00", "airline": "BL", "price": 650000},
            {"time": "15:30", "airline": "VJ", "price": 790000},
            {"time": "18:00", "airline": "VN", "price": 1090000},
        ],
    },
    ("DAD", "HAN"): {
        "duration": 80,
        "flights": [
            {"time": "07:00", "airline": "VJ", "price": 690000},
            {"time": "09:00", "airline": "VN", "price": 990000},
            {"time": "11:00", "airline": "QH", "price": 850000},
            {"time": "14:00", "airline": "BL", "price": 650000},
            {"time": "16:30", "airline": "VJ", "price": 790000},
            {"time": "19:00", "airline": "VN", "price": 1090000},
        ],
    },
}


def generate_mock_result(
    origin: str,
    destination: str,
    date: str,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
) -> dict[str, Any]:
    """Generate realistic mock SearchFlight response.

    Matches the AGT API format so format_flight_results can consume it.
    """
    route_key = (origin.upper(), destination.upper())
    route = ROUTES.get(route_key)

    if not route:
        # Try reverse route
        route = ROUTES.get((destination.upper(), origin.upper()))
        if route:
            origin, destination = destination, origin
        else:
            return {
                "Success": True,
                "StatusCode": "OK",
                "Message": "Không có dữ liệu cho tuyến này",
                "ListGroup": [],
            }

    duration = route["duration"]
    flights = route["flights"]

    # Build AGT-compatible groups
    # Each group = 1 airline, contains air_options → flight_options → flights
    seen_airlines = set()
    groups = []
    group_no = 0

    for f in flights:
        airline = f["airline"]
        flight_num = f"{airline}{random.randint(*AIRLINES[airline]['range'])}"

        # Calculate arrival time
        dep_h, dep_m = map(int, f["time"].split(":"))
        dep_total = dep_h * 60 + dep_m
        arr_total = dep_total + duration
        if arr_total >= 1440:
            arr_total -= 1440
        arr_h, arr_m = arr_total // 60, arr_total % 60
        arrive_str = f"{arr_h:02d}:{arr_m:02d}"

        # Always create a new group (matches how AGT returns per-airline results)
        group_no += 1
        group = {
            "GroupId": f"GRP{group_no:03d}",
            "System": 1,
            "ListAirOption": [
                {
                    "AirOptionId": f"OPT{group_no:03d}",
                    "Price": float(f["price"]),
                    "Currency": "VND",
                    "FareClass": "ECONOMY",
                    "Seats": random.choice([3, 5, 7, 9]),
                    "ListFlightOption": [
                        {
                            "FlightOptionId": f"FO{group_no:03d}",
                            "Leg": 0,
                            "ListFlight": [
                                {
                                    "FlightId": f"FL{group_no:03d}",
                                    "Airline": airline,
                                    "FlightNumber": str(flight_num),
                                    "StartPoint": origin,
                                    "EndPoint": destination,
                                    "DepartDate": f"{date} {f['time']}",
                                    "ArriveDate": f"{date} {arrive_str}",
                                    "Leg": 0,
                                    "StopNum": 0,
                                    "Seats": random.choice([3, 5, 7, 9]),
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        groups.append(group)

    # Mark cheapest
    if groups:
        cheapest = min(groups, key=lambda g: g["ListAirOption"][0]["Price"])
        cheapest["ListAirOption"][0]["FareClass"] = "PROMOTION"

    return {
        "Success": True,
        "StatusCode": "OK",
        "Message": "Success",
        "ListGroup": groups,
        "Extra": {
            "Adt": adults,
            "Chd": children,
            "Inf": infants,
        },
    }
