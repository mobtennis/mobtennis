"""Map upstream country names → ISO3 codes used by Player.country_code.

api-tennis returns country names ("Poland", "United States"); flag rendering
on the web side speaks ISO3. This is the bridge. Limited to nations with
historical tennis presence; unknowns return None (sync layer leaves NULL).
"""

# Lowercase keys for lookup tolerance.
_NAME_TO_ISO3: dict[str, str] = {
    "usa": "USA", "united states": "USA", "united states of america": "USA", "u.s.a.": "USA",
    "great britain": "GBR", "united kingdom": "GBR", "uk": "GBR", "britain": "GBR", "england": "GBR",
    "spain": "ESP", "france": "FRA", "italy": "ITA", "germany": "GER",
    "switzerland": "SUI", "austria": "AUT", "serbia": "SRB", "croatia": "CRO",
    "russia": "RUS", "belarus": "BLR", "poland": "POL", "czech republic": "CZE", "czechia": "CZE",
    "slovakia": "SVK", "bulgaria": "BUL", "greece": "GRE", "denmark": "DEN",
    "sweden": "SWE", "norway": "NOR", "finland": "FIN", "netherlands": "NED",
    "belgium": "BEL", "portugal": "POR", "ukraine": "UKR", "australia": "AUS",
    "new zealand": "NZL", "japan": "JPN", "china": "CHN", "south korea": "KOR", "korea": "KOR",
    "taiwan": "TPE", "chinese taipei": "TPE", "hong kong": "HKG",
    "india": "IND", "thailand": "THA", "kazakhstan": "KAZ", "uzbekistan": "UZB",
    "canada": "CAN", "mexico": "MEX", "brazil": "BRA", "argentina": "ARG",
    "chile": "CHI", "colombia": "COL", "peru": "PER", "uruguay": "URU",
    "south africa": "RSA", "tunisia": "TUN", "egypt": "EGY", "morocco": "MAR",
    "israel": "ISR", "turkey": "TUR", "lebanon": "LIB", "hungary": "HUN",
    "romania": "ROU", "latvia": "LAT", "lithuania": "LTU", "estonia": "EST",
    "slovenia": "SLO", "bosnia and herzegovina": "BIH", "montenegro": "MNE",
    "moldova": "MDA", "georgia": "GEO", "armenia": "ARM", "azerbaijan": "AZE",
    "ireland": "IRL", "iceland": "ISL", "luxembourg": "LUX",
    "venezuela": "VEN", "ecuador": "ECU", "paraguay": "PAR", "bolivia": "BOL",
    "dominican republic": "DOM", "cuba": "CUB",
    "philippines": "PHI", "indonesia": "INA", "vietnam": "VIE", "malaysia": "MAS",
    "singapore": "SGP", "iran": "IRI", "saudi arabia": "KSA", "uae": "UAE",
    "united arab emirates": "UAE", "qatar": "QAT", "kuwait": "KUW",
    "puerto rico": "PUR", "north macedonia": "MKD", "kosovo": "KOS",
    "cyprus": "CYP", "malta": "MLT", "monaco": "MON", "san marino": "SMR",
    "albania": "ALB",
}


def name_to_iso3(name: str | None) -> str | None:
    if not name:
        return None
    return _NAME_TO_ISO3.get(name.strip().lower())
