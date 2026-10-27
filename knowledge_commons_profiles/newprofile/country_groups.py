"""
Named groups of countries for member statistics

Countries are identified by ISO 3166-1 alpha-2 codes, which is how the ROR
data set (and therefore UserStats.countries) records them. Group membership
is a pragmatic editorial choice rather than an official taxonomy; the
docstring on each group explains the basis used.
"""

import re

_NORMALISE = re.compile(r"[^a-z0-9]+")


class UnknownGroupError(ValueError):
    """
    Raised when a requested country group does not exist
    """


COUNTRY_NAMES: dict[str, str] = {
    "AD": "Andorra",
    "AE": "United Arab Emirates",
    "AF": "Afghanistan",
    "AG": "Antigua and Barbuda",
    "AI": "Anguilla",
    "AL": "Albania",
    "AM": "Armenia",
    "AO": "Angola",
    "AQ": "Antarctica",
    "AR": "Argentina",
    "AS": "American Samoa",
    "AT": "Austria",
    "AU": "Australia",
    "AW": "Aruba",
    "AX": "Åland Islands",
    "AZ": "Azerbaijan",
    "BA": "Bosnia and Herzegovina",
    "BB": "Barbados",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BF": "Burkina Faso",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BI": "Burundi",
    "BJ": "Benin",
    "BL": "Saint Barthélemy",
    "BM": "Bermuda",
    "BN": "Brunei",
    "BO": "Bolivia",
    "BQ": "Bonaire, Sint Eustatius and Saba",
    "BR": "Brazil",
    "BS": "Bahamas",
    "BT": "Bhutan",
    "BV": "Bouvet Island",
    "BW": "Botswana",
    "BY": "Belarus",
    "BZ": "Belize",
    "CA": "Canada",
    "CC": "Cocos (Keeling) Islands",
    "CD": "Democratic Republic of the Congo",
    "CF": "Central African Republic",
    "CG": "Republic of the Congo",
    "CH": "Switzerland",
    "CI": "Côte d'Ivoire",
    "CK": "Cook Islands",
    "CL": "Chile",
    "CM": "Cameroon",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CU": "Cuba",
    "CV": "Cabo Verde",
    "CW": "Curaçao",
    "CX": "Christmas Island",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DJ": "Djibouti",
    "DK": "Denmark",
    "DM": "Dominica",
    "DO": "Dominican Republic",
    "DZ": "Algeria",
    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "EH": "Western Sahara",
    "ER": "Eritrea",
    "ES": "Spain",
    "ET": "Ethiopia",
    "FI": "Finland",
    "FJ": "Fiji",
    "FK": "Falkland Islands",
    "FM": "Micronesia",
    "FO": "Faroe Islands",
    "FR": "France",
    "GA": "Gabon",
    "GB": "United Kingdom",
    "GD": "Grenada",
    "GE": "Georgia",
    "GF": "French Guiana",
    "GG": "Guernsey",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GL": "Greenland",
    "GM": "Gambia",
    "GN": "Guinea",
    "GP": "Guadeloupe",
    "GQ": "Equatorial Guinea",
    "GR": "Greece",
    "GS": "South Georgia and the South Sandwich Islands",
    "GT": "Guatemala",
    "GU": "Guam",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    "HK": "Hong Kong",
    "HM": "Heard Island and McDonald Islands",
    "HN": "Honduras",
    "HR": "Croatia",
    "HT": "Haiti",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IM": "Isle of Man",
    "IN": "India",
    "IO": "British Indian Ocean Territory",
    "IQ": "Iraq",
    "IR": "Iran",
    "IS": "Iceland",
    "IT": "Italy",
    "JE": "Jersey",
    "JM": "Jamaica",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KI": "Kiribati",
    "KM": "Comoros",
    "KN": "Saint Kitts and Nevis",
    "KP": "North Korea",
    "KR": "South Korea",
    "KW": "Kuwait",
    "KY": "Cayman Islands",
    "KZ": "Kazakhstan",
    "LA": "Laos",
    "LB": "Lebanon",
    "LC": "Saint Lucia",
    "LI": "Liechtenstein",
    "LK": "Sri Lanka",
    "LR": "Liberia",
    "LS": "Lesotho",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "LY": "Libya",
    "MA": "Morocco",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MF": "Saint Martin",
    "MG": "Madagascar",
    "MH": "Marshall Islands",
    "MK": "North Macedonia",
    "ML": "Mali",
    "MM": "Myanmar",
    "MN": "Mongolia",
    "MO": "Macao",
    "MP": "Northern Mariana Islands",
    "MQ": "Martinique",
    "MR": "Mauritania",
    "MS": "Montserrat",
    "MT": "Malta",
    "MU": "Mauritius",
    "MV": "Maldives",
    "MW": "Malawi",
    "MX": "Mexico",
    "MY": "Malaysia",
    "MZ": "Mozambique",
    "NA": "Namibia",
    "NC": "New Caledonia",
    "NE": "Niger",
    "NF": "Norfolk Island",
    "NG": "Nigeria",
    "NI": "Nicaragua",
    "NL": "Netherlands",
    "NO": "Norway",
    "NP": "Nepal",
    "NR": "Nauru",
    "NU": "Niue",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PF": "French Polynesia",
    "PG": "Papua New Guinea",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PM": "Saint Pierre and Miquelon",
    "PN": "Pitcairn",
    "PR": "Puerto Rico",
    "PS": "Palestine",
    "PT": "Portugal",
    "PW": "Palau",
    "PY": "Paraguay",
    "QA": "Qatar",
    "RE": "Réunion",
    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russia",
    "RW": "Rwanda",
    "SA": "Saudi Arabia",
    "SB": "Solomon Islands",
    "SC": "Seychelles",
    "SD": "Sudan",
    "SE": "Sweden",
    "SG": "Singapore",
    "SH": "Saint Helena, Ascension and Tristan da Cunha",
    "SI": "Slovenia",
    "SJ": "Svalbard and Jan Mayen",
    "SK": "Slovakia",
    "SL": "Sierra Leone",
    "SM": "San Marino",
    "SN": "Senegal",
    "SO": "Somalia",
    "SR": "Suriname",
    "SS": "South Sudan",
    "ST": "São Tomé and Príncipe",
    "SV": "El Salvador",
    "SX": "Sint Maarten",
    "SY": "Syria",
    "SZ": "Eswatini",
    "TC": "Turks and Caicos Islands",
    "TD": "Chad",
    "TF": "French Southern Territories",
    "TG": "Togo",
    "TH": "Thailand",
    "TJ": "Tajikistan",
    "TK": "Tokelau",
    "TL": "Timor-Leste",
    "TM": "Turkmenistan",
    "TN": "Tunisia",
    "TO": "Tonga",
    "TR": "Türkiye",
    "TT": "Trinidad and Tobago",
    "TV": "Tuvalu",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "UA": "Ukraine",
    "UG": "Uganda",
    "UM": "United States Minor Outlying Islands",
    "US": "United States",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VA": "Vatican City",
    "VC": "Saint Vincent and the Grenadines",
    "VE": "Venezuela",
    "VG": "British Virgin Islands",
    "VI": "United States Virgin Islands",
    "VN": "Vietnam",
    "VU": "Vanuatu",
    "WF": "Wallis and Futuna",
    "WS": "Samoa",
    "YE": "Yemen",
    "YT": "Mayotte",
    "ZA": "South Africa",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}


def _codes(spec: str) -> frozenset[str]:
    """
    Turn a whitespace-separated string of ISO codes into a frozenset
    """
    return frozenset(spec.split())


# --- Geographic regions -----------------------------------------------------

NORTH_AFRICA = _codes("DZ EG LY MA TN EH")

SUB_SAHARAN_AFRICA = _codes(
    "AO BJ BW BF BI CM CV CF TD KM CG CD CI DJ GQ ER SZ ET GA GM GH GN GW "
    "KE LS LR MG MW ML MR MU YT MZ NA NE NG RE RW ST SN SC SL SO ZA SS SD "
    "TZ TG UG ZM ZW SH"
)

AFRICA = NORTH_AFRICA | SUB_SAHARAN_AFRICA

CARIBBEAN = _codes(
    "AG AI AW BB BL BQ BS CU CW DM DO GD GP HT JM KN KY LC MF MQ MS PR SX "
    "TC TT VC VG VI BZ GY SR"
)

CENTRAL_AMERICA = _codes("BZ CR GT HN NI PA SV")

SOUTH_AMERICA = _codes("AR BO BR CL CO EC FK GF GY PE PY SR UY VE")

LATIN_AMERICA = _codes(
    "MX GT HN SV NI CR PA CO VE EC PE BO BR PY UY AR CL CU DO HT PR GF"
)

LATIN_AMERICA_AND_CARIBBEAN = (
    LATIN_AMERICA | CARIBBEAN | CENTRAL_AMERICA | SOUTH_AMERICA
)

NORTH_AMERICA = _codes("US CA MX GL BM PM")

EUROPEAN_UNION = _codes(
    "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO "
    "SK SI ES SE"
)

EUROPE = EUROPEAN_UNION | _codes(
    "AL AD AX BA BY CH FO GB GG GI IM IS JE LI MC MD ME MK NO RS RU SJ SM "
    "UA VA"
)

NORDIC = _codes("DK FI IS NO SE FO GL AX SJ")

BALTIC = _codes("EE LV LT")

MIDDLE_EAST = _codes(
    "AE BH IL IQ IR JO KW LB OM PS QA SA SY TR YE"
)

MENA = MIDDLE_EAST - _codes("TR") | NORTH_AFRICA | _codes("DJ")

CENTRAL_ASIA = _codes("KZ KG TJ TM UZ")

CAUCASUS = _codes("AM AZ GE")

SOUTH_ASIA = _codes("AF BD BT IN MV NP PK LK")

EAST_ASIA = _codes("CN HK MO TW JP KR KP MN")

INDO_CHINA = _codes("VN LA KH TH MM")

SOUTHEAST_ASIA = INDO_CHINA | _codes("BN ID MY PH SG TL")

ASIA = (
    MIDDLE_EAST
    | CENTRAL_ASIA
    | CAUCASUS
    | SOUTH_ASIA
    | EAST_ASIA
    | SOUTHEAST_ASIA
    | _codes("IO")
) - _codes("CY")

OCEANIA = _codes(
    "AU NZ FJ PG SB VU WS TO KI TV NR FM MH PW NC PF GU AS CK NU TK WF NF "
    "PN MP CC CX UM HM"
)

# --- Economic / political groupings ----------------------------------------

# Loosely the Brandt-line "North": Europe (including Russia), Canada, the
# United States and Greenland, plus Japan, South Korea, Israel, Australia
# and New Zealand. Everything else is the "South".
GLOBAL_NORTH = (
    EUROPE
    | _codes("US CA GL BM PM")
    | _codes("JP KR IL AU NZ")
    | _codes("AQ BV GS TF")
)

GLOBAL_SOUTH = (
    frozenset(COUNTRY_NAMES) - GLOBAL_NORTH
)

G7 = _codes("CA FR DE IT JP GB US")

G20 = _codes(
    "AR AU BR CA CN FR DE IN ID IT JP MX RU SA ZA KR TR GB US"
)

BRICS = _codes("BR RU IN CN ZA EG ET IR AE ID")

OECD = _codes(
    "AU AT BE CA CL CO CR CZ DK EE FI FR DE GR HU IS IE IL IT JP KR LV LT "
    "LU MX NL NZ NO PL PT SK SI ES SE CH TR GB US"
)

COMMONWEALTH = _codes(
    "AG AU BS BD BB BZ BW BN CM CA CY DM FJ GA GM GH GD GY IN JM KE KI LS "
    "MW MY MV MT MU MZ NA NR NZ NG PK PG RW WS SC SL SG SB ZA LK KN LC VC "
    "SZ TZ TG TO TT TV UG GB VU ZM"
)

# --- Linguistic groupings ---------------------------------------------------

# Countries and territories where English is an official or de facto
# national language.
ANGLOPHONE = _codes(
    "US GB IE CA AU NZ "
    "JM TT BB BS BZ GY AG DM GD KN LC VC AI BM VG KY MS TC VI PR "
    "NG GH KE UG TZ ZA ZM ZW BW MW NA SL LR GM SZ LS RW CM SS MU SC SH "
    "IN PK SG PH HK MT GI IM GG JE FK "
    "FJ PG WS TO VU SB KI TV NR FM MH PW GU AS MP NF CK NU TK PN"
)

FRANCOPHONE = _codes(
    "FR BE CH LU MC CA HT "
    "BJ BF BI CM CF TD KM CG CD CI DJ GQ GA GN MG ML NE RW SN SC TG "
    "VU MU LB DZ MA TN "
    "GF GP MQ RE YT NC PF PM WF BL MF"
)

LUSOPHONE = _codes("PT BR AO MZ CV GW ST TL GQ MO")

HISPANOPHONE = _codes(
    "ES MX GT HN SV NI CR PA CO VE EC PE BO PY UY AR CL CU DO PR GQ"
)

ARAB_WORLD = _codes(
    "DZ BH KM DJ EG IQ JO KW LB LY MR MA OM PS QA SA SO SD SY TN AE YE EH"
)


COUNTRY_GROUPS: dict[str, frozenset[str]] = {
    "World": frozenset(COUNTRY_NAMES),
    "Global South": GLOBAL_SOUTH,
    "Global North": GLOBAL_NORTH,
    "Europe": EUROPE,
    "European Union": EUROPEAN_UNION,
    "Nordic": NORDIC,
    "Baltic": BALTIC,
    "North America": NORTH_AMERICA,
    "Latin America": LATIN_AMERICA,
    "Caribbean": CARIBBEAN,
    "Latin America and the Caribbean": LATIN_AMERICA_AND_CARIBBEAN,
    "Central America": CENTRAL_AMERICA,
    "South America": SOUTH_AMERICA,
    "Africa": AFRICA,
    "North Africa": NORTH_AFRICA,
    "Sub-Saharan Africa": SUB_SAHARAN_AFRICA,
    "Middle East": MIDDLE_EAST,
    "Middle East and North Africa": MENA,
    "Asia": ASIA,
    "Central Asia": CENTRAL_ASIA,
    "Caucasus": CAUCASUS,
    "South Asia": SOUTH_ASIA,
    "East Asia": EAST_ASIA,
    "Southeast Asia": SOUTHEAST_ASIA,
    "Indo-China": INDO_CHINA,
    "Oceania": OCEANIA,
    "Anglophone": ANGLOPHONE,
    "Francophone": FRANCOPHONE,
    "Lusophone": LUSOPHONE,
    "Hispanophone": HISPANOPHONE,
    "Arab World": ARAB_WORLD,
    "Commonwealth": COMMONWEALTH,
    "G7": G7,
    "G20": G20,
    "BRICS": BRICS,
    "OECD": OECD,
}

# Alternative names and abbreviations, matched after normalisation
GROUP_ALIASES: dict[str, str] = {
    "EU": "European Union",
    "MENA": "Middle East and North Africa",
    "English-speaking": "Anglophone",
    "English": "Anglophone",
    "French-speaking": "Francophone",
    "French": "Francophone",
    "Spanish-speaking": "Hispanophone",
    "Spanish": "Hispanophone",
    "Portuguese-speaking": "Lusophone",
    "Portuguese": "Lusophone",
    "Arabic-speaking": "Arab World",
    "Arabic": "Arab World",
    "Arab League": "Arab World",
    "Majority World": "Global South",
    "Developing World": "Global South",
    "Developed World": "Global North",
    "LatAm": "Latin America",
    "LAC": "Latin America and the Caribbean",
    "SSA": "Sub-Saharan Africa",
    "West Asia": "Middle East",
    "SE Asia": "Southeast Asia",
    "Mainland Southeast Asia": "Indo-China",
    "Indochinese Peninsula": "Indo-China",
    "Scandinavia": "Nordic",
    "West Indies": "Caribbean",
    "Pacific": "Oceania",
    "Australasia": "Oceania",
    "Everywhere": "World",
    "All": "World",
    "Global": "World",
}


def _normalise(name: str) -> str:
    """
    Reduce a group name to lower-case alphanumerics so that case, spacing
    and punctuation do not matter when matching
    """
    return _NORMALISE.sub("", name.lower())


_GROUPS_BY_KEY: dict[str, str] = {
    _normalise(name): name for name in COUNTRY_GROUPS
}
_ALIASES_BY_KEY: dict[str, str] = {
    _normalise(alias): name for alias, name in GROUP_ALIASES.items()
}


def resolve_group(name: str) -> tuple[str, frozenset[str]]:
    """
    Find a country group by name or alias, ignoring case and punctuation

    :param name: the requested group name
    :return: the canonical group name and its set of ISO codes
    :raises UnknownGroupError: if no group matches
    """
    key = _normalise(name)

    canonical = _GROUPS_BY_KEY.get(key) or _ALIASES_BY_KEY.get(key)

    if canonical is None:
        raise UnknownGroupError(name)

    return canonical, COUNTRY_GROUPS[canonical]


def group_member_counts(
    codes: frozenset[str],
    counts: dict[str, int],
    *,
    include_zero: bool = False,
) -> list[tuple[str, str, int]]:
    """
    Pair each country in a group with its member count

    :param codes: the ISO codes making up the group
    :param counts: member counts keyed by ISO code
    :param include_zero: whether to keep countries with no members
    :return: (code, country name, count) tuples, most members first and
        alphabetical by name within equal counts
    """
    rows = [
        (code, COUNTRY_NAMES.get(code, code), int(counts.get(code, 0)))
        for code in codes
    ]

    if not include_zero:
        rows = [row for row in rows if row[2] > 0]

    return sorted(rows, key=lambda row: (-row[2], row[1]))


def country_group_breakdown(counts: dict[str, int]) -> list[dict]:
    """
    Summarise every group for the dashboard, alphabetically by name

    :param counts: member counts keyed by ISO code
    :return: one dict per group with its name, the countries that have
        members (as code/name/count dicts, most members first), the member
        total and the number of countries that make up the group
    """
    breakdown = []

    for name in sorted(COUNTRY_GROUPS, key=str.casefold):
        rows = group_member_counts(COUNTRY_GROUPS[name], counts)

        breakdown.append(
            {
                "name": name,
                "countries": [
                    {"code": code, "name": country, "count": count}
                    for code, country, count in rows
                ],
                "total": sum(count for _, _, count in rows),
                "size": len(COUNTRY_GROUPS[name]),
            }
        )

    return breakdown
