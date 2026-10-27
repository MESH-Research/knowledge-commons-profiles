# Country Groups: Sources and Editorial Decisions

> **Note**: This document describes the country groups defined in
> `knowledge_commons_profiles/newprofile/country_groups.py`, used by the
> `country_group_stats` management command and the "Members by Region or
> Group" section of the stats dashboard. Membership lists were last reviewed
> in October 2026.

## What is being counted

The stats build (`build_stats`) records, for each member whose institution has
been matched to a Research Organization Registry (ROR) record, the ISO 3166-1
alpha-2 country code of that ROR record. The dashboard and the command roll
those codes up into named groups. Two consequences follow:

- A member is counted under the country of their **institution**, not their
  nationality or residence.
- Members without a ROR-matched institution are not counted anywhere. The
  "share of all located members" figure on the dashboard uses the total of all
  ROR-matched members (the `World` group) as its denominator.

Country codes and names follow ISO 3166-1. Where ISO has changed a short name
the current form is used: Türkiye, Czechia, Eswatini, Cabo Verde, North
Macedonia, Timor-Leste. Some ISO entries are uninhabited or near-uninhabited
territories (Bouvet Island, Heard Island and McDonald Islands, the French
Southern Territories and so on). They are kept in the table so that any code
ROR emits can be named, and they are placed in the geographically obvious
group; they will never carry members.

Kosovo has no ISO 3166-1 code. ROR uses the user-assigned code `XK` for its
Kosovo organisations (28 records, including the University of Prishtina, as
of October 2026), so `XK` is included in the names table as "Kosovo" and is
placed in `Europe` and therefore `Global North`. It is the one non-ISO code in
the table.

## How the lists were compiled

The lists were compiled by hand against the standard reference lists named
below, rather than imported from a data file, so that the editorial choices
are explicit and reviewable in one place. When a reference list changes
(a new EU member, a BRICS accession, a Commonwealth departure) the code must be
updated by hand and this document amended. The references are:

| Reference | Used for |
| --- | --- |
| [ISO 3166-1](https://www.iso.org/iso-3166-country-codes.html) | Codes and short names |
| [UN M49 geoscheme](https://unstats.un.org/unsd/methodology/m49/) | Continental and sub-regional boundaries (Europe, Africa, Asia, Oceania, the Americas and their sub-regions) |
| [World Bank country classification](https://datahelpdesk.worldbank.org/knowledgebase/articles/906519) | Middle East and North Africa, Sub-Saharan Africa, Latin America and the Caribbean |
| [Brandt Report (1980)](https://en.wikipedia.org/wiki/Brandt_Report) and [Group of 77 membership](https://www.g77.org/doc/members.html) | Global North / Global South |
| [European Union member states](https://european-union.europa.eu/principles-countries-history/eu-countries_en) | European Union |
| [Commonwealth member countries](https://thecommonwealth.org/our-member-countries) | Commonwealth |
| [OECD members](https://www.oecd.org/en/about/members-partners.html) | OECD |
| [G7](https://www.g7.utoronto.ca/) and [G20](https://www.g20.org/) | G7, G20 |
| [BRICS](https://brics.br/en) | BRICS |
| [Arab League members](https://en.wikipedia.org/wiki/Member_states_of_the_Arab_League) | Arab World |
| [Organisation internationale de la Francophonie](https://www.francophonie.org/) and national language law | Francophone |
| [Community of Portuguese Language Countries](https://www.cplp.org/) | Lusophone |

Language groups are not simply the membership of the corresponding
international organisation, because those bodies admit observers and
associate members on political rather than linguistic grounds. The basis used
for each is given below.

## The groups

### Geographic regions

These follow the UN M49 geoscheme unless noted. Groups are built from smaller
sets in the code (for example `Latin America and the Caribbean` is the union
of `Latin America`, `Caribbean`, `Central America` and `South America`) so that
overlapping groups stay consistent with one another.

| Group | Basis and judgement calls |
| --- | --- |
| **World** | Every ISO 3166-1 code. Used as the denominator for shares. |
| **Europe** | UN M49 Europe, including Russia, Belarus, Ukraine and Moldova, the Western Balkans, the microstates and the Crown Dependencies, Faroe Islands, Gibraltar, Svalbard and Åland, and Kosovo under ROR's `XK`. **Cyprus** is included because it is an EU member, although M49 places it in Western Asia. Türkiye, Armenia, Azerbaijan, Georgia and Kazakhstan are not included. |
| **European Union** | The 27 member states as of 2026. Does not include EFTA states, candidates or the UK. |
| **Nordic** | Denmark, Finland, Iceland, Norway and Sweden plus the Faroe Islands, Greenland, Svalbard and Åland. Greenland is therefore in both `Nordic` and `North America`. |
| **Baltic** | Estonia, Latvia, Lithuania. |
| **North America** | United States, Canada, Mexico, Greenland, Bermuda, Saint Pierre and Miquelon (M49 Northern America plus Mexico). Mexico is also in `Latin America`. |
| **Latin America** | The Spanish- and Portuguese-speaking mainland states plus the Hispanophone and Francophone Caribbean (Cuba, Dominican Republic, Haiti, Puerto Rico) and French Guiana. Belize, Guyana and Suriname are not included here; they appear under `Caribbean` because they are CARICOM members. |
| **Caribbean** | The island states and territories of the Caribbean, plus Belize, Guyana and Suriname as CARICOM members. Includes dependent territories (Anguilla, Montserrat, the Dutch Caribbean, the French Antilles, the US and British Virgin Islands, Cayman Islands, Turks and Caicos). |
| **Latin America and the Caribbean** | Union of the above with `Central America` and `South America`, matching the World Bank and UN LAC region. The Falkland Islands are included through `South America`. |
| **Central America** | Belize, Costa Rica, El Salvador, Guatemala, Honduras, Nicaragua, Panama. |
| **South America** | The twelve sovereign states plus French Guiana and the Falkland Islands. |
| **Africa** | Union of `North Africa` and `Sub-Saharan Africa`. |
| **North Africa** | Algeria, Egypt, Libya, Morocco, Tunisia and Western Sahara. Sudan is placed in Sub-Saharan Africa, following the World Bank rather than M49. |
| **Sub-Saharan Africa** | World Bank SSA, including Sudan, Mauritania, Somalia and Djibouti, plus the Indian Ocean and Atlantic territories (Mayotte, Réunion, Saint Helena). |
| **Middle East** | The Gulf states, the Levant, Iran, Iraq, Israel, Palestine, Yemen and **Türkiye**. Egypt and Cyprus are not included. |
| **Middle East and North Africa** | Follows the World Bank MENA grouping: the Middle East *without* Türkiye, plus North Africa and Djibouti. Malta, which the World Bank includes, is left in Europe. |
| **Asia** | M49 Asia: the Middle East (with Türkiye), the Caucasus, Central, South, East and Southeast Asia, and the British Indian Ocean Territory. Cyprus is excluded (see Europe) and Russia is counted in Europe. |
| **Central Asia** | Kazakhstan, Kyrgyzstan, Tajikistan, Turkmenistan, Uzbekistan. |
| **Caucasus** | Armenia, Azerbaijan, Georgia. |
| **South Asia** | The eight SAARC members: Afghanistan, Bangladesh, Bhutan, India, Maldives, Nepal, Pakistan, Sri Lanka. |
| **East Asia** | China, Hong Kong, Macao, Taiwan, Japan, North and South Korea, Mongolia. Hong Kong, Macao and Taiwan are separate because ROR assigns them their own ISO codes. |
| **Southeast Asia** | The ten ASEAN members plus Timor-Leste. |
| **Indo-China** | The mainland Southeast Asian states: Vietnam, Laos, Cambodia (the former French Indochina) plus Thailand and Myanmar, which share the Indochinese Peninsula. Peninsular Malaysia is not separable from Malaysia and so Malaysia is left out. |
| **Oceania** | Australia, New Zealand, the Pacific island states and the Pacific territories of France, the US and New Zealand, plus Australia's external territories. |

### Economic and political groupings

| Group | Basis and judgement calls |
| --- | --- |
| **Global North** | A Brandt-line reading: all of `Europe` (including Russia, Ukraine, Belarus, Moldova and the Balkans), the United States, Canada, Greenland, Bermuda and Saint Pierre and Miquelon, Japan, South Korea, Israel, Australia and New Zealand, plus the Antarctic and sub-Antarctic territories. |
| **Global South** | Everything not in `Global North`. This matches the broad Group of 77 plus China usage and so treats Singapore, Hong Kong, Taiwan, the Gulf states, Türkiye, the Caucasus and Central Asia as South even though several are high income. South Korea is counted as North, reflecting its OECD membership, although it is not a G77 member either way. The two groups are disjoint by construction and together cover every code. |
| **G7** | Canada, France, Germany, Italy, Japan, the United Kingdom and the United States. The EU participates but is not a country. |
| **G20** | The nineteen member countries. The European Union and the African Union are members but are not countries and so are not listed; their member states are counted only if they are members in their own right. |
| **BRICS** | Brazil, Russia, India, China, South Africa, and the members admitted in 2024 and 2025: Egypt, Ethiopia, Iran, the United Arab Emirates and Indonesia. Saudi Arabia was invited but has not formally completed accession and is left out. Partner countries are not included. |
| **OECD** | The 38 members as of 2026. Accession candidates are not included. |
| **Commonwealth** | The 56 members as of 2026, including Gabon and Togo (joined 2022). Gabon remains listed despite its partial suspension in 2023. |

### Language groups

| Group | Basis and judgement calls |
| --- | --- |
| **Anglophone** | Countries and territories where English is an official language at national level or the de facto language of government and higher education. This includes India, Pakistan, the Philippines, Singapore, Hong Kong, Malta, Cameroon and Rwanda (co-official), the Anglophone Caribbean and Pacific, and British and US territories. Puerto Rico is included because English is co-official. Malaysia, Bangladesh, Sri Lanka, Sudan, Ethiopia and Israel are excluded because English has no official status or a very limited one. |
| **Francophone** | Countries and territories where French is an official language, plus the Maghreb (Algeria, Morocco, Tunisia) and Lebanon, where French has no official status but remains a principal language of higher education and research. OIF members whose French use is marginal (Egypt, Vietnam, Cambodia, Laos, Greece, Romania and others) are excluded. Mauritania is excluded although French remains widely used administratively; this is a borderline call. |
| **Lusophone** | The nine CPLP member states (Portugal, Brazil, Angola, Mozambique, Cabo Verde, Guinea-Bissau, São Tomé and Príncipe, Timor-Leste and Equatorial Guinea) plus Macao, where Portuguese is co-official. |
| **Hispanophone** | The twenty countries where Spanish is an official or national language, plus Puerto Rico. Equatorial Guinea is therefore in three language groups. |
| **Arab World** | The 22 Arab League members plus Western Sahara. Comoros, Djibouti and Somalia are included as League members although Arabic is a minority language in each. |

## Aliases

The command and the lookup helper accept the following alternative names in
addition to the canonical ones. Matching ignores case, spacing and
punctuation, so `indochina`, `Indo China` and `indo-china` all resolve.

| Alias | Group |
| --- | --- |
| All, Everywhere, Global | World |
| EU | European Union |
| MENA | Middle East and North Africa |
| West Asia | Middle East |
| SE Asia | Southeast Asia |
| Mainland Southeast Asia, Indochinese Peninsula | Indo-China |
| LatAm | Latin America |
| LAC | Latin America and the Caribbean |
| West Indies | Caribbean |
| SSA | Sub-Saharan Africa |
| Scandinavia | Nordic |
| Pacific, Australasia | Oceania |
| Majority World, Developing World | Global South |
| Developed World | Global North |
| English, English-speaking | Anglophone |
| French, French-speaking | Francophone |
| Spanish, Spanish-speaking | Hispanophone |
| Portuguese, Portuguese-speaking | Lusophone |
| Arabic, Arabic-speaking, Arab League | Arab World |

Scandinavia is strictly Denmark, Norway and Sweden; it is mapped to the wider
Nordic group as the more useful approximation for member statistics.

## Changing a group

1. Edit the relevant set in `country_groups.py`. Groups that are unions of
   smaller sets should be changed through the smaller set so that the related
   groups stay consistent.
2. Update the table above with the reason for the change and the date it was
   checked against the reference list.
3. Run the `newprofile` tests. `test_country_group_stats` checks that every
   code has a name, that Global North and South do not overlap, and that every
   group and alias in the code is mentioned in this document.
