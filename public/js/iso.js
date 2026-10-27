// ISO 3166-1 alpha-2 -> [numeric, name] for the countries in Netflix's public Top 10 country list.
// world-atlas 110m uses the numeric id, so the choropleth joins on it. Small territories
// (Guadeloupe, Martinique, Reunion, Hong Kong, Maldives, Malta, Mauritius, Bahrain, Singapore)
// are too small for the 110m outline and are only visible in the table.
export const ISO = {
  AE: [784, "United Arab Emirates"], AR: [32, "Argentina"], AT: [40, "Austria"], AU: [36, "Australia"],
  AZ: [31, "Azerbaijan"], BD: [50, "Bangladesh"], BE: [56, "Belgium"], BG: [100, "Bulgaria"],
  BH: [48, "Bahrain"], BO: [68, "Bolivia"], BR: [76, "Brazil"], BS: [44, "Bahamas"],
  CA: [124, "Canada"], CH: [756, "Switzerland"], CL: [152, "Chile"], CO: [170, "Colombia"],
  CR: [188, "Costa Rica"], CY: [196, "Cyprus"], CZ: [203, "Czechia"], DE: [276, "Germany"],
  DK: [208, "Denmark"], DO: [214, "Dominican Republic"], EC: [218, "Ecuador"], EE: [233, "Estonia"],
  EG: [818, "Egypt"], ES: [724, "Spain"], FI: [246, "Finland"], FR: [250, "France"],
  GB: [826, "United Kingdom"], GH: [288, "Ghana"], GP: [312, "Guadeloupe"], GR: [300, "Greece"],
  GT: [320, "Guatemala"], HK: [344, "Hong Kong"], HN: [340, "Honduras"], HR: [191, "Croatia"],
  HU: [348, "Hungary"], ID: [360, "Indonesia"], IE: [372, "Ireland"], IL: [376, "Israel"],
  IN: [356, "India"], IS: [352, "Iceland"], IT: [380, "Italy"], JM: [388, "Jamaica"],
  JO: [400, "Jordan"], JP: [392, "Japan"], KE: [404, "Kenya"], KR: [410, "South Korea"],
  KW: [414, "Kuwait"], LB: [422, "Lebanon"], LK: [144, "Sri Lanka"],
  LT: [440, "Lithuania"], LU: [442, "Luxembourg"], LV: [428, "Latvia"], MA: [504, "Morocco"],
  MQ: [474, "Martinique"], MT: [470, "Malta"], MU: [480, "Mauritius"], MV: [462, "Maldives"],
  MX: [484, "Mexico"], MY: [458, "Malaysia"], NG: [566, "Nigeria"], NI: [558, "Nicaragua"],
  NL: [528, "Netherlands"], NO: [578, "Norway"], NZ: [554, "New Zealand"], OM: [512, "Oman"],
  PA: [591, "Panama"], PE: [604, "Peru"], PH: [608, "Philippines"], PK: [586, "Pakistan"],
  PL: [616, "Poland"], PT: [620, "Portugal"], PY: [600, "Paraguay"], QA: [634, "Qatar"],
  RE: [638, "Reunion"], RO: [642, "Romania"], RS: [688, "Serbia"], RU: [643, "Russia"],
  SA: [682, "Saudi Arabia"], SE: [752, "Sweden"], SG: [702, "Singapore"], SI: [705, "Slovenia"],
  SK: [703, "Slovakia"], TH: [764, "Thailand"], TR: [792, "Turkey"], TT: [780, "Trinidad and Tobago"],
  TW: [158, "Taiwan"], UA: [804, "Ukraine"], US: [840, "United States"], UY: [858, "Uruguay"],
  VE: [862, "Venezuela"], VN: [704, "Vietnam"], ZA: [710, "South Africa"],
};
export const NUMERIC_TO_CODE = Object.fromEntries(Object.entries(ISO).map(([c, [n]]) => [n, c]));

// [lon, lat] for the territories world-atlas 110m has no outline for, so the map can still mark them.
export const MICRO_LONLAT = {
  BH: [50.55, 26.07], GP: [-61.55, 16.25], HK: [114.17, 22.32], MQ: [-61.0, 14.64], MT: [14.38, 35.9],
  MU: [57.55, -20.35], MV: [73.5, 4.2], RE: [55.53, -21.12], SG: [103.82, 1.35],
};
