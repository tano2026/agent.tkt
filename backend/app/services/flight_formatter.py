"""
Flight result formatter — biến AGT API response thành card chat đẹp.

AGT response structure:
  ListGroup[] → ListAirOption[] (có Price, Currency)
              → ListFlightOption[] → ListFlight[] (có Airline, FlightNumber, DepartDate...)
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.aviation_db import get_airport_info

logger = logging.getLogger(__name__)


def format_flight_results(data: dict[str, Any], params: dict[str, Any] | None = None, return_data: bool = False) -> str | tuple[str, list]:
    """Format AGT SearchFlight response → human-readable chat message.
    
    If return_data=True, returns (text, structured_flights_list).
    structured_flights_list is a list of dicts for frontend rendering.
    """
    if not data.get("Success", False):
        msg = f"❌ Không tìm được chuyến bay: {data.get('Message', 'Lỗi không xác định')}"
        return (msg, []) if return_data else msg

    groups = data.get("ListGroup", [])
    if not groups:
        msg = "😔 Không tìm thấy chuyến bay nào phù hợp. Bạn thử đổi ngày khác nhé?"
        return (msg, []) if return_data else msg

    # Extract route info
    origin_code = (params or {}).get("origin", "")
    dest_code = (params or {}).get("destination", "")
    origin_info = get_airport_info(origin_code)
    dest_info = get_airport_info(dest_code)
    origin_city = origin_info["city"] if origin_info else origin_code
    dest_city = dest_info["city"] if dest_info else dest_code
    # Use shorter names for known cities
    city_short = {"Hồ Chí Minh": "TP.HCM"}
    origin_city = city_short.get(origin_city, origin_city)
    dest_city = city_short.get(dest_city, dest_city)

    date_str = (params or {}).get("date", "")
    date_formatted = f"{date_str[0:2]}/{date_str[2:4]}/{date_str[4:8]}" if date_str and len(date_str) == 8 else ""

    header = f"✈️ **{origin_city} → {dest_city}**"
    if date_formatted:
        header += f" | {date_formatted}"
    header += "\n\n"

    # Parse flights from AGT structure
    parsed = []
    for group in groups:
        for air_option in group.get("ListAirOption", []):
            price = float(air_option.get("Price", 0) or 0)
            currency = air_option.get("Currency", "VND")
            fare_class = air_option.get("FareClass", "")
            seats = air_option.get("Seats", 0)

            for flight_option in air_option.get("ListFlightOption", []):
                for flight in flight_option.get("ListFlight", []):
                    # Parse time from "03072026 0455" format
                    depart_raw = flight.get("DepartDate", "")
                    arrive_raw = flight.get("ArriveDate", "")
                    depart_time = depart_raw.split()[-1] if " " in str(depart_raw) else depart_raw
                    arrive_time = arrive_raw.split()[-1] if " " in str(arrive_raw) else arrive_raw

                    parsed.append({
                        "airline": flight.get("Airline", ""),
                        "flight_number": flight.get("FlightNumber", ""),
                        "start_point": flight.get("StartPoint", ""),
                        "end_point": flight.get("EndPoint", ""),
                        "depart_time": depart_time,
                        "arrive_time": arrive_time,
                        "depart_date": depart_raw[:8] if depart_raw else "",
                        "price": price,
                        "currency": currency,
                        "fare_class": fare_class,
                        "leg": flight.get("Leg", 0),
                        "seats": seats,
                        "stop_num": flight.get("StopNum", 0),
                    })

    if not parsed:
        return f"{header}😔 Không tìm thấy chuyến bay nào."

    # Sort by price. Store raw AGT option data for selection later.
    sorted_options = []
    # AGT API can return duplicate flight *options* if different fare classes have same flight.
    # Group by unique flight/time/price to avoid showing duplicates to user, but keep AGT unique IDs.
    seen_flights_display = set() # (airline, flight_num, depart_time, arrive_time, price)
    idx = 1
    for group in groups:
        for air_option in group.get("ListAirOption", []):
            price = float(air_option.get("Price", 0) or 0)
            currency = air_option.get("Currency", "VND")
            
            # Find the actual flight details from ListFlightOption.ListFlight
            flight_details = None
            for flight_option in air_option.get("ListFlightOption", []):
                if flight_option.get("ListFlight"):
                    flight_details = flight_option["ListFlight"][0]
                    break
            
            if not flight_details:
                logger.warning(f"No flight details found for air_option: {air_option.get('AirlineOptionId')}")
                continue

            airline = flight_details.get("Airline", "")
            flight_number = flight_details.get("FlightNumber", "")
            depart_time = flight_details.get("DepartDate", "").split()[-1][:5] if " " in str(flight_details.get("DepartDate", "")) else ""
            arrive_time = flight_details.get("ArriveDate", "").split()[-1][:5] if " " in str(flight_details.get("ArriveDate", "")) else ""

            display_key = (airline, flight_number, depart_time, arrive_time, price)

            if display_key not in seen_flights_display:
                seen_flights_display.add(display_key)
                # Store full AGT option IDs for booking
                sorted_options.append({
                    "idx": idx, # User-facing index
                    "airline": airline,
                    "flight_number": flight_number,
                    "depart_time": depart_time,
                    "arrive_time": arrive_time,
                    "price": price,
                    "currency": currency,
                    "all_option_ids": { # The specific combo needed for BookFlight/GetAncillary
                        "Session": air_option.get("Session", ""),
                        "AirlineOptionId": air_option.get("AirlineOptionId", 0),
                        "FareOptionId": flight_option.get("FareOptionId", 0), # FareOptionId is in flight_option
                        "FlightOptionId": flight_option.get("FlightOptionId", 0), # FlightOptionId is in flight_option
                    },
                    "seats": air_option.get("Seats", 0),
                    "stops": flight_details.get("StopNum", 0),
                    "raw_air_option": air_option, # For full detail if needed
                    "raw_flight_details": flight_details, # For full detail if needed
                })
                idx += 1
    
    # Actually sort the collected flights by price
    sorted_options.sort(key=lambda x: x["price"])

    if not sorted_options:
        msg = f"{header}😔 Không tìm thấy chuyến bay nào phù hợp sau khi lọc trùng. Bạn thử đổi ngày khác nhé?"
        return (msg, []) if return_data else msg
    
    cheapest = sorted_options[0]["price"]

    # Build lines for display
    lines = []
    airline_colors = {
        "VN": "🔵", "VJ": "🔴", "QH": "🟢", "VU": "🟠", "9G": "🟣",
        "BL": "⚪", "MH": "🔴", "SQ": "🟡", "EK": "🔴", "QR": "🟣",
    }
    structured_flights_list = [] # For return_data, containing full details
    for f_option in sorted_options[:10]: # Display top 10
        al = f_option["airline"]
        fn = f_option["flight_number"]
        dep = f_option["depart_time"]
        arr = f_option["arrive_time"]

        flight_code = f"{al}{fn}"
        if fn.upper().startswith(al.upper()):
            flight_code = f"{al}{fn[len(al):]}"
        elif fn.upper() == al.upper():
            flight_code = al
        
        # Truncate to max 7 chars for table alignment
        if len(flight_code) > 7:
            flight_code = flight_code[:7]

        price_str = f"{int(f_option['price']):,}₫"
        
        emoji = airline_colors.get(al, "✈️")
        tags = []
        if f_option["price"] == cheapest:
            tags.append("⭐")
        dur_h = _get_duration_hours(f_option["depart_time"], f_option["arrive_time"])
        dur_str = f" ({dur_h}h)" if dur_h else ""

        # Prepend user-facing index
        idx_str = f"[{f_option['idx']}] ".ljust(5)

        # Table row with fixed widths
        # Format: [idx] emoji code    dep → arr     price        dur
        code_part = flight_code.ljust(8)
        time_part = f"{dep} → {arr}".ljust(16)
        price_part = price_str.rjust(14)
        dur_part = dur_str.ljust(8)
        line = f"{idx_str}{emoji} {code_part}{time_part}{price_part}  {dur_part}"
        if tags:
            line += " " + " ".join(tags)
        lines.append(line)

        # Build structured data for return_data output
        structured_flights_list.append({
            "index": f_option['idx'],
            "airline": al,
            "code": flight_code,
            "depart": f_option["depart_time"],
            "arrive": f_option["arrive_time"],
            "price": f_option["price"],
            "price_str": price_str,
            "cheapest": f_option["price"] == cheapest,
            "duration_h": dur_h,
            "seats": f_option["seats"],
            "stops": f_option["stops"],
            "all_option_ids": f_option["all_option_ids"], # Include the booking IDs
        })

    # Build table format with code block (wider layout, header matches column widths)
    header_row = "      " + "Mã số".ljust(8) + "Giờ đi → Đến".ljust(16) + "Giá".rjust(14) + "    " + "Bay"
    sep_row =    "────" + "─" * 7 + " " + "─" * 15 + " " + "─" * 14 + " " + "─" * 7
    body = header + "```\n"
    body += header_row + "\n"
    body += sep_row + "\n"
    for line in lines:
        body += line + "\n"
    body += "```\n"
    # Footer
    adults = (params or {}).get("adults", 1)
    children = (params or {}).get("children", 0)
    total = adults + children
    body += f"\n💰 Rẻ nhất: **{int(cheapest):,}₫**"
    if total > 1:
        body += f" | 👥 {adults} NL{' + ' + str(children) + ' TE' if children else ''}"
        body += f" | **Tổng: {int(cheapest * total):,}₫**"
    
    # Add selection instructions
    body += "\n\n👉 **Chọn chuyến bay:** Gõ `chọn` [số thứ tự] hoặc `đặt` [mã chuyến bay]"
    body += "\n   (VD: `chọn 1` hoặc `đặt BL360`)"

    if return_data:
        return body, structured_flights_list
    return body
    lines = []
    airline_colors = {
        "VN": "🔵", "VJ": "🔴", "QH": "🟢", "VU": "🟠", "9G": "🟣",
        "BL": "⚪", "MH": "🔴", "SQ": "🟡", "EK": "🔴", "QR": "🟣",
    }
    for f in parsed[:10]:
        al = f["airline"]
        fn = f["flight_number"]
        dep = f["depart_time"][:5] if len(f["depart_time"]) >= 5 else f["depart_time"]
        arr = f["arrive_time"][:5] if len(f["arrive_time"]) >= 5 else f["arrive_time"]

        # Fix: airline code may already contain the full code (e.g. "BL" not "BLBL")
        # flight_number sometimes already includes airline prefix
        flight_code = f"{al}{fn}"
        # Deduplicate: if fn starts with al, remove al prefix
        if fn.upper().startswith(al.upper()):
            flight_code = f"{al}{fn[len(al):]}"
        elif fn.upper() == al.upper():
            flight_code = al
        # Truncate to max 7 chars for table alignment
        if len(flight_code) > 7:
            flight_code = flight_code[:7]

        if f["currency"] == "VND":
            price_str = f"{int(f['price']):,}₫"
        else:
            price_str = f"{f['price']:,.2f} {f['currency']}"

        emoji = airline_colors.get(al, "✈️")
        tags = []
        if f["price"] == cheapest:
            tags.append("⭐")
        dur = _get_duration_hours(f["depart_time"], f["arrive_time"])
        dur_str = f" ({dur}h)" if dur else ""

        # Table row with fixed widths (wider layout for readability)
        # Format: emoji code    dep → arr     price        dur
        code_part = flight_code.ljust(8)
        time_part = f"{dep} → {arr}".ljust(16)
        price_part = price_str.rjust(14)
        dur_part = dur_str.ljust(8)
        line = f"{emoji} {code_part}{time_part}{price_part}  {dur_part}"
        if tags:
            line += " " + " ".join(tags)
        lines.append(line)

    # Build structured flight data for frontend
    flight_data_list = []
    for f in parsed[:10]:
        al = f["airline"]
        fn = f["flight_number"]
        flight_code = f"{al}{fn}"
        if fn.upper().startswith(al.upper()):
            flight_code = f"{al}{fn[len(al):]}"
        elif fn.upper() == al.upper():
            flight_code = al
        flight_data_list.append({
            "airline": al,
            "code": flight_code,
            "depart": f["depart_time"][:5] if len(f["depart_time"]) >= 5 else f["depart_time"],
            "arrive": f["arrive_time"][:5] if len(f["arrive_time"]) >= 5 else f["arrive_time"],
            "price": f["price"],
            "price_str": f"{int(f['price']):,}₫",
            "cheapest": f["price"] == cheapest,
            "duration_h": _get_duration_hours(f["depart_time"], f["arrive_time"]),
            "seats": f["seats"],
        })

    # Build table format with code block (wider layout, header matches column widths)
    header_row = "  " + "Mã số".ljust(8) + "Giờ đi → Đến".ljust(16) + "Giá".rjust(14) + "    " + "Bay"
    sep_row = "  " + "─" * 7 + " " + "─" * 15 + " " + "─" * 14 + " " + "─" * 7
    body = header + "```\n"
    body += header_row + "\n"
    body += sep_row + "\n"
    for line in lines:
        body += line + "\n"
    body += "```\n"
    # Footer
    adults = (params or {}).get("adults", 1)
    children = (params or {}).get("children", 0)
    total = adults + children
    body += f"\n💰 Rẻ nhất: **{int(cheapest):,}₫**"
    if total > 1:
        body += f" | 👥 {adults} NL{' + ' + str(children) + ' TE' if children else ''}"
        body += f" | **Tổng: {int(cheapest * total):,}₫**"

    if return_data:
        return body, flight_data_list
    return body


def _get_hour(time_str: str) -> int:
    if not time_str or ":" not in str(time_str):
        return 12
    try:
        return int(time_str.split(":")[0])
    except (ValueError, IndexError):
        return 12


def _get_duration_hours(depart: str, arrive: str) -> int:
    if ":" not in str(depart) or ":" not in str(arrive):
        return 0
    try:
        dh, dm = depart.split(":")
        ah, am = arrive.split(":")
        d_min = int(dh) * 60 + int(dm)
        a_min = int(ah) * 60 + int(am)
        if a_min < d_min:
            a_min += 1440
        return round((a_min - d_min) / 60)
    except (ValueError, IndexError):
        return 0
