const services = [
  ['⌂', 'Real Estate', 'Buy, sell or rent property in India.', true],
  ['▦', 'Property Management', 'Reliable care for your home back in India.'],
  ['⚖', 'Legal & Taxation', 'Expert legal and tax support for NRIs.'],
  ['↗', 'Wealth Management', 'Plan and manage your wealth securely.'],
  ['▤', 'Documentation', 'Help with paperwork and attestations.'],
  ['♡', 'Healthcare', 'Find trusted doctors and care.'],
  ['✈', 'Travel & Tourism', 'Plan your next trip to India.'],
  ['ϟ', 'Essential Utilities', 'Bills and essential services in one place.'],
  ['⌑', 'Education', 'Support for schools and student needs.'],
  ['₹', 'Remittances', 'Send money home simply and securely.'],
  ['❀', 'Weddings & Events', 'Plan your celebrations in India.'],
  ['◎', 'Immigration', 'Visa and immigration guidance.']
];

const SQUARE_YARDS_ENDPOINT = 'https://sy-mcp.squareyards.com/mcp/external';
const MP_RERA_SEARCH_ENDPOINT = 'https://www.rera.mp.gov.in/projectsrcg-loop.php';
const MP_RERA_ORIGIN = 'https://www.rera.mp.gov.in';
// Keep the live Square Yards demo usable before the first city catalog import.
// Imported database cities replace this fallback as soon as they are available.
const FALLBACK_CITIES = ['Indore'];
let CITIES = [];
const MAX_RESULTS = 20;

function cityOptions(selectedCity = '') {
  if (!CITIES.length) return '<option value="">No imported cities available</option>';
  return CITIES.map(city => `<option value="${esc(city)}" ${city === selectedCity ? 'selected' : ''}>${esc(city)}</option>`).join('');
}
// Curated external project references found on property marketing/consultancy sites.
// These confirm that a project is mentioned/listed on the source site; they do not
// guarantee that a unit is still available. Prefer direct unit links where known.
const INDORE_PARTNER_PROJECTS = [
  { id: '315715', name: 'Apollo DB City', locality: 'Nipania', imageMatch: 'apollo-db-city', status: 'Sale and rental listings found', links: [
    { label: 'Total Realty · Buy listings', url: 'https://totalrealtysolutions.org/buy/', type: 'Listings page' },
    { label: 'Total Realty · Rent listings', url: 'https://totalrealtysolutions.org/rent/', type: 'Listings page' },
    { label: 'Housing.com · 2 BHK rental', url: 'https://housing.com/rent/13299829-1363-sqft-2-bhk-apartment-on-rent-in-nipania-indore-v2', type: 'Unit listing' },
    { label: 'Housing.com · 3 BHK rental', url: 'https://housing.com/rent/20448312-1982-sqft-3-bhk-apartment-on-rent-in-nipania-indore', type: 'Unit listing' },
    { label: 'Housing.com · Plot for sale', url: 'https://housing.com/buy-4265-sqft-residential-plot-in-nipania-for-rs-64000000-rid-17575828-v2', type: 'Unit listing' }
  ] },
  { id: '315399', name: 'Lifestyle Ocean Park', locality: 'Nipania', imageMatch: 'lifestyle-ocean-park', status: 'Sale and rental listings found', links: [
    { label: 'Total Realty · Buy listings', url: 'https://totalrealtysolutions.org/buy/', type: 'Listings page' },
    { label: 'Total Realty · Rent listings', url: 'https://totalrealtysolutions.org/rent/', type: 'Listings page' },
    { label: 'Housing.com · Project and resale listings', url: 'https://housing.com/in/buy/indore/nipania-gid/projects/ocean-park-pid/', type: 'Listings page' },
    { label: 'Housing.com · 3 BHK for sale', url: 'https://housing.com/buy-1540-sqft-3-bhk-apartment-in-nipania-for-rs-9200000-rid-20978855', type: 'Unit listing' }
  ] },
  { id: '315514', name: 'BCM Planet', locality: 'Nipania / Tulsi Nagar', imageMatch: 'bcm-planet', status: 'Resale and rental listings found', links: [
    { label: 'Total Realty · Rent listings', url: 'https://totalrealtysolutions.org/rent/', type: 'Listings page' },
    { label: 'Housing.com · Resale listings', url: 'https://housing.com/in/buy/indore/nipania-gid/projects/bcm-planet-phase-1-pid/', type: 'Listings page' },
    { label: 'Housing.com · Rental listings', url: 'https://housing.com/rent-bcm-planet-phase-1-for-rent-in-nipania-indore-rpid-AGgnAH0', type: 'Listings page' }
  ] },
  { id: '315422', name: 'Saakaar Atlanta Aura', locality: 'Nipania', imageMatch: 'atlanta-aura', status: 'Sale and rental listings found', links: [
    { label: 'Total Realty · Buy listings', url: 'https://totalrealtysolutions.org/buy/', type: 'Listings page' },
    { label: 'Total Realty · Rent listings', url: 'https://totalrealtysolutions.org/rent/', type: 'Listings page' },
    { label: 'Total Realty · 3 BHK for sale', url: 'https://totalrealtysolutions.org/property/wwe79wo1ih27mwi', type: 'Unit listing' },
    { label: 'Housing.com · Resale listings', url: 'https://housing.com/in/buy/indore/nipania-gid/projects/atlanta-aura-pid/', type: 'Listings page' },
    { label: 'Housing.com · Rental listings', url: 'https://housing.com/rent-atlanta-aura-for-rent-in-nipania-indore-rpid-AG4bbgAH0', type: 'Listings page' }
  ] },
  { id: '315410', name: 'Shikhar Balaji Skyz', locality: 'Nipania', imageMatch: 'shikhar-balaji-skyz', status: 'Rental listings found', links: [
    { label: 'Total Realty · Rent listings', url: 'https://totalrealtysolutions.org/rent/', type: 'Listings page' },
    { label: 'Housing.com · Project and unit listings', url: 'https://housing.com/buy-shikhar-balaji-skyz-by-shikhar-housing-development-pvt-ltd-in-nipania-indore-pid-6611', type: 'Project page' }
  ] },
  { id: '315654', name: 'Siddhivinayak Maple Woods', locality: 'Pipliya Kumar / Nipania', imageMatch: 'maple-woods', status: 'Agent sale listing found', links: [
    { label: 'Dreams To Reality · 2 BHK sale listing', url: 'https://www.realestateindia.com/property-detail/residential-flats-apartments/sell/2-bedrooms-in-nipania-indore-madhya-pradesh-634215.htm', type: 'Unit listing' },
    { label: 'Dreams To Reality · Agent profile', url: 'https://www.realestateindia.com/profile/dreams-to-reality-in-indore-1080547/', type: 'Agent profile' }
  ] },
  { id: '315526', name: 'Royal Greens', locality: 'Niranjanpur', imageMatch: 'royal-greens', status: 'Sale listing and project page found', links: [
    { label: 'Indoprops · Project page', url: 'https://indoprops.com/projects/royal-greens/', type: 'Project page' },
    { label: 'Housing.com · 3 BHK for sale', url: 'https://housing.com/buy-1700-sqft-3-bhk-apartment-in-lasudia-mori-for-rs-6600000-rid-12298682-v2', type: 'Unit listing' },
    { label: 'Housing.com · Project page', url: 'https://housing.com/buy-royal-greens-by-man-developer-in-shakkar-khedi-indore-pid-19402', type: 'Project page' }
  ] },
  { id: '316116', name: 'Shekhar Unity', locality: 'Pipliyahana', imageMatch: 'shekhar-unity', status: 'Project pages found; unit availability not confirmed', links: [
    { label: 'Indoprops · Project page', url: 'https://indoprops.com/projects/shekar-unity/', type: 'Project page' },
    { label: 'Housing.com · Project page', url: 'https://housing.com/buy-shekhar-unity-by-shekhar-construction-in-pipliyahana-indore-pid-299013', type: 'Project page' }
  ] },
  { id: '315649', name: 'Palazzo Park Residences', locality: 'Indore', imageMatch: 'no-confirmed-squareyards-image', status: 'Union Bank approved-project list reference found', financeReference: true, links: [
    { label: 'Union Bank of India · Approved project PDF', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', type: 'Bank project reference' }
  ] },
  { id: '315642', name: 'Shivneri Sahil Empire', locality: 'Indore', imageMatch: 'no-confirmed-squareyards-image', status: 'Union Bank approved-project list reference found', financeReference: true, links: [
    { label: 'Union Bank of India · Approved project PDF', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', type: 'Bank project reference' }
  ] },
  { id: '316449', name: 'Prosperity Sky Meridian', locality: 'Indore', imageMatch: 'no-confirmed-squareyards-image', status: 'Union Bank approved-project list reference found', financeReference: true, links: [
    { label: 'Union Bank of India · Approved project PDF', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', type: 'Bank project reference' }
  ] },
  { id: '315382', name: 'DB Pride', locality: 'Indore', imageMatch: 'no-confirmed-squareyards-image', status: 'Union Bank approved-project list reference found', financeReference: true, links: [
    { label: 'Union Bank of India · Approved project PDF', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', type: 'Bank project reference' }
  ] },
  { id: '316430', name: 'JRK Ghanshyam Castle', locality: 'Indore', imageMatch: 'no-confirmed-squareyards-image', status: 'Union Bank approved-project list reference found', financeReference: true, links: [
    { label: 'Union Bank of India · Approved project PDF', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', type: 'Bank project reference' }
  ] },
  { id: '344400', name: 'Emerald Horizon Tower', locality: 'Bicholi Hapsi', developer: 'Agarwal Real City Private Limited', status: 'PNB housing-project reference found', financeReference: true, links: [
    { label: 'Punjab National Bank · Housing projects', url: 'https://pnb.bank.in/housing-projects.aspx', type: 'Bank project reference' },
    { label: 'Square Yards · Emerald Horizon Tower', url: 'https://www.squareyards.com/emerald-horizon-tower-bicholi-hapsi-indore-npd-344400', type: 'Project page' }
  ] },
  { id: '344577', name: 'JMG Landmark Palms', locality: 'Indore', developer: 'JMG Infraprojects', status: 'PNB housing-project reference found', financeReference: true, links: [
    { label: 'Punjab National Bank · Housing projects', url: 'https://pnb.bank.in/housing-projects.aspx', type: 'Bank project reference' }
  ] },
  { id: '315377', name: 'Agarwal Emerald Gateway', locality: 'Indore', developer: 'Agarwal Realinfra LLP', status: 'PNB housing-project reference found', financeReference: true, links: [
    { label: 'Punjab National Bank · Housing projects', url: 'https://pnb.bank.in/housing-projects.aspx', type: 'Bank project reference' }
  ] },
  { id: '344128', name: 'Nirvana Landmark', locality: 'Indore', developer: 'Nirvana Realty', status: 'PNB housing-project reference found', financeReference: true, links: [
    { label: 'Punjab National Bank · Housing projects', url: 'https://pnb.bank.in/housing-projects.aspx', type: 'Bank project reference' }
  ] },
  { id: '340639', name: 'Godrej Verdania Estate', locality: 'Indore', developer: 'Godrej Projects Development Limited', status: 'PNB housing-project reference found', financeReference: true, links: [
    { label: 'Punjab National Bank · Housing projects', url: 'https://pnb.bank.in/housing-projects.aspx', type: 'Bank project reference' }
  ] },
  { id: '344129', name: 'Nirvana Skydeck', locality: 'Indore', developer: 'Nirvana Realty', status: 'PNB housing-project reference found', financeReference: true, links: [
    { label: 'Punjab National Bank · Housing projects', url: 'https://pnb.bank.in/housing-projects.aspx', type: 'Bank project reference' }
  ] },
  { id: '315798', name: 'Sugan Residency', locality: 'Mog Lines', imageMatch: 'no-confirmed-squareyards-image', status: 'Locality infrastructure record found', links: [
    { label: 'Square Yards · Sugan Residency', url: 'https://www.squareyards.com/indore-residential-property/sugan-residency/315798/project', type: 'Project page' }
  ] },
  { id: '316456', name: 'Vibrant Trishla Apartments', locality: 'Rajwada', imageMatch: 'no-confirmed-squareyards-image', status: 'Rajwada ABD infrastructure records found', links: [
    { label: 'Square Yards · Vibrant Trishla Apartments', url: 'https://www.squareyards.com/indore-residential-property/vibrant-trishla-apartments/316456/project', type: 'Project page' }
  ] }
];
// Bank-published Indore project references supplied/checked during research.
// These confirm a project-name listing, not a home-loan guarantee for a buyer or unit.
const INDORE_FINANCE_PROJECTS = [
  { id: '315422', name: 'Saakaar Atlanta Aura', banks: [
    { bank: 'Union Bank of India', listed: 'Atlanta Aura', builder: 'Not shown in supplied excerpt', status: 'Exact project-name match', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', source: 'Approved project PDF' },
    { bank: 'Axis Bank', listed: 'ATLANTA AURA', builder: 'SAAKAAR M B GROUP', code: 'AXISPAS000086', status: 'Exact project-name match', url: 'https://application.axis.bank.in/webforms/ApprovedProjectList/homeloans_request.aspx', source: 'Approved project search' }
  ] },
  { id: '315649', name: 'Palazzo Park Residences', banks: [
    { bank: 'Union Bank of India', listed: 'Palazzo Park Residences', status: 'Listed in supplied bank excerpt', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', source: 'Approved project PDF' }
  ] },
  { id: '315642', name: 'Shivneri Sahil Empire', banks: [
    { bank: 'Union Bank of India', listed: 'Shivneri Sahil Empire', status: 'Listed in supplied bank excerpt', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', source: 'Approved project PDF' }
  ] },
  { id: '316449', name: 'Prosperity Sky Meridian', banks: [
    { bank: 'Union Bank of India', listed: 'Prosperity Sky Meridian', status: 'Listed in supplied bank excerpt', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', source: 'Approved project PDF' }
  ] },
  { id: '315382', name: 'DB Pride', banks: [
    { bank: 'Union Bank of India', listed: 'DB Pride', status: 'Listed in supplied bank excerpt', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', source: 'Approved project PDF' }
  ] },
  { id: '316430', name: 'JRK Ghanshyam Castle', banks: [
    { bank: 'Union Bank of India', listed: 'JRK Ghanshyam Castle', status: 'Listed in supplied bank excerpt', url: 'https://www.unionbankofindia.bank.in/pdf/pdf-of-builder.pdf', source: 'Approved project PDF' }
  ] },
  { id: '315526', name: 'Royal Greens', banks: [
    { bank: 'Axis Bank', listed: 'ROYAL GREENS PART OF ROYAL AMAR GREENS PHASE III', builder: 'MAN DEVELOPMENTS', code: 'INDPAS059779', status: 'Name/phase match', url: 'https://application.axis.bank.in/webforms/ApprovedProjectList/homeloans_request.aspx', source: 'Approved project search' }
  ], possibleBanks: [
    { bank: 'Canara Bank', listed: 'ROYAL AMAR GREENS – PHASE III', code: 'PRJ000010255', status: 'Possible phase/name variant; confirm with builder', url: 'https://www.canarabank.bank.in/housing-projects', source: 'Housing projects list' }
  ] },
  { id: '316116', name: 'Shekhar Unity', banks: [
    { bank: 'Axis Bank', listed: 'SHEKHAR UNITY', builder: 'SHEKHAR CONSTRUCTION', code: 'INDPAS068436', status: 'Exact project-name match', url: 'https://application.axis.bank.in/webforms/ApprovedProjectList/homeloans_request.aspx', source: 'Approved project search' },
    { bank: 'Canara Bank', listed: 'SHEKHAR UNITY', code: 'PRJ00015368', status: 'Exact project-name match', url: 'https://www.canarabank.bank.in/housing-projects', source: 'Housing projects list' }
  ] },
  { id: '344400', name: 'Emerald Horizon Tower', banks: [
    { bank: 'Punjab National Bank', listed: 'Emerald Horizon Tower', builder: 'Agarwal Real City Private Limited', status: 'Listed in supplied PNB housing-project reference', url: 'https://pnb.bank.in/housing-projects.aspx', source: 'Housing projects list' }
  ] },
  { id: '344577', name: 'JMG Landmark Palms', banks: [
    { bank: 'Punjab National Bank', listed: 'Landmark Palms', builder: 'JMG Infraprojects', status: 'Square Yards match to supplied PNB project list', url: 'https://pnb.bank.in/housing-projects.aspx', source: 'Housing projects list' }
  ] },
  { id: '315377', name: 'Agarwal Emerald Gateway', banks: [
    { bank: 'Punjab National Bank', listed: 'Emerald Gateway', builder: 'Agarwal Realinfra LLP', status: 'Square Yards match to supplied PNB project list', url: 'https://pnb.bank.in/housing-projects.aspx', source: 'Housing projects list' }
  ] },
  { id: '344128', name: 'Nirvana Landmark', banks: [
    { bank: 'Punjab National Bank', listed: 'Landmark', builder: 'Nirvana Realty', status: 'Square Yards match to supplied PNB project list', url: 'https://pnb.bank.in/housing-projects.aspx', source: 'Housing projects list' }
  ] },
  { id: '340639', name: 'Godrej Verdania Estate', banks: [
    { bank: 'Punjab National Bank', listed: 'Verdania Estate', builder: 'Godrej Projects Development Limited', status: 'Square Yards match to supplied PNB project list', url: 'https://pnb.bank.in/housing-projects.aspx', source: 'Housing projects list' }
  ] },
  { id: '344129', name: 'Nirvana Skydeck', banks: [
    { bank: 'Punjab National Bank', listed: 'SKYDECK', builder: 'Nirvana Realty', status: 'Square Yards match to supplied PNB project list', url: 'https://pnb.bank.in/housing-projects.aspx', source: 'Housing projects list' }
  ] }
];
let state = {
  city: '',
  bhk: '',
  maxBudget: 50000000,
  possessionStatus: '',
  completionYear: '',
  buildingType: '1',
  query: '',
  projects: [],
  total: 0,
  loading: false,
  loaded: false,
  error: '',
  requestNumber: 0,
  page: 1,
  recommendationMode: false,
  recommendationLoading: false,
  recommendationError: '',
  recommendationData: null
};
const projectDetailsCache = new Map();
const recommendationImageCache = new Map();
const recommendationImageRequests = new Map();
const detailRequests = new Map();
const projectRecordCache = new Map();
const projectRecordRequests = new Map();
const projectRecordErrors = new Map();
const financierCache = new Map();
const financierRequests = new Map();
const financierErrors = new Map();
const priceTrendCache = new Map();
const priceTrendRequests = new Map();
const priceTrendErrors = new Map();
const infrastructureCache = new Map();
const infrastructureRequests = new Map();
const infrastructureErrors = new Map();
const developerDetailsCache = new Map();
const developerRequests = new Map();
const developerErrors = new Map();
const mpReraCache = new Map([
  ['P-OTH-24-4694', { name: 'SIDDHI VINAYAK RESIDENCY BLOCK-B', type: 'New', districtArea: 'Indore - Other', number: 'P-OTH-24-4694', validity: '01-09-2022 to 21-08-2025', status: 'In Progress' }],
  ['P-IND-26-6368', { name: 'SIDDHI VINAYAK RESIDENCY BLOCK-A', type: 'New', districtArea: 'Indore - Indore', number: 'P-IND-26-6368', validity: '01-09-2024 to 22-09-2026', status: 'In Progress' }],
  ['P-SWR-24-5289', { name: 'LANDMARK', type: 'New', districtArea: 'Indore - Sanwer', number: 'P-SWR-24-5289', validity: '01-05-2024 to 28-04-2027', status: 'In Progress' }],
  ['P-SWR-24-5278', { name: 'SKYDECK', type: 'New', districtArea: 'Indore - Sanwer', number: 'P-SWR-24-5278', validity: '01-08-2024 to 22-07-2027', status: 'In Progress' }]
]);
const mpReraRequests = new Map();
const mpReraErrors = new Map();
const rajasthanReraCache = new Map();
const rajasthanReraRequests = new Map();
const rajasthanReraErrors = new Map();
const gujaratReraCache = new Map();
const gujaratReraRequests = new Map();
const gujaratReraErrors = new Map();
const app = document.getElementById('app');

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

function money(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 'Any budget';
  if (number >= 10000000) return `₹${(number / 10000000).toFixed(number % 10000000 ? 2 : 0)} Cr`;
  return `₹${(number / 100000).toFixed(number % 100000 ? 0 : 0)} L`;
}

function header(active = 'Home') {
  return `<div class="announcement">A MORE PERSONAL WAY TO TAKE CARE OF INDIA <span>✦</span> MADE FOR NRIs, WITH CARE</div>
  <header class="header"><a class="brand" href="/">NRI<span style="color:var(--gold)">EASE</span><em>.COM</em></a>
    <nav class="nav"><a class="${active === 'Home' ? 'active' : ''}" href="/">Home</a><a href="/#services">Services</a><a href="/#how">How it works</a><a href="javascript:void(0)" class="disabled-link">Partners</a><a href="javascript:void(0)" class="disabled-link">About</a></nav>
    <div class="nav-right"><button class="icon-btn" aria-label="Search" onclick="location.href='/real-estate'">⌕</button><button class="btn btn-gold" onclick="openModal('Enquire about a service')">ENQUIRE</button><button class="btn btn-outline" onclick="toast('Login will be available in a future release.')">LOGIN</button></div>
  </header>`;
}

function footer() {
  return `<footer class="footer"><div class="shell"><div class="footer-grid"><div><a class="brand" href="/">NRI<span style="color:#d1ad61">EASE</span><em>.COM</em></a><p>Your trusted concierge for every NRI need in India.<br>Real people. Trusted partners. Hassle-free support.</p></div><div><div class="footer-title">Explore</div><a href="/#services">Services</a><a href="/#how">How it works</a><a href="javascript:void(0)">Our story</a></div><div><div class="footer-title">Contact</div><a href="javascript:void(0)" onclick="openModal('Talk to our concierge')">Talk to a concierge</a><a href="javascript:void(0)" onclick="openModal('Raise an enquiry')">Help centre</a><a href="javascript:void(0)">Feedback</a></div><div><div class="footer-title">Information</div><a href="javascript:void(0)">Privacy policy</a><a href="javascript:void(0)">Terms of use</a><a href="javascript:void(0)">Disclaimer</a></div></div><div class="copyright">© 2026 NRIEASE.COM. All rights reserved. <span style="float:right">Made for the journey home.</span></div></div></footer>`;
}

function home() {
  return `${header('Home')}<main><div class="shell"><section class="hero"><div><div class="eyebrow">Your life in India, made easier</div><h1>Your trusted concierge for every NRI need in India.</h1><p class="hero-copy">From finding a home to taking care of the details, we make it simpler to stay close to the place you call home.</p><div class="hero-actions"><a class="btn btn-gold" href="#services">EXPLORE SERVICES　→</a><button class="btn btn-outline" onclick="openModal('Talk to our concierge')">☏ &nbsp;TALK TO A CONCIERGE</button></div></div><div class="hero-art"><img src="https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1100&q=85" alt="A modern home in India"><div class="art-label">A little closer to home <span style="color:var(--gold)">✦</span></div></div></section>
  <div class="searchbar"><input id="home-search" placeholder="⌕　Project name (optional)" /><select id="home-city">${cityOptions(state.city)}</select><button class="btn btn-gold" onclick="searchProperties()">SEARCH　⌕</button></div>
  <section class="services" id="services"><div class="section-head"><div class="eyebrow" style="justify-content:center">Thoughtfully connected</div><h2>All services in one place</h2><p>Choose the support you need, wherever life takes you.</p></div><div class="service-grid">${services.map(([icon, name, desc, enabled]) => `<div class="service-card ${enabled ? 'active' : 'disabled'}" ${enabled ? 'onclick="location.href=\'/real-estate\'"' : 'aria-disabled="true" title="Coming soon"'}><span class="service-icon">${icon}</span><strong>${name}</strong><p>${desc}</p><span class="service-link">${enabled ? 'EXPLORE →' : 'COMING SOON'}</span></div>`).join('')}</div></section></div>
  <section class="strip"><div class="shell strip-inner"><div><strong>Looking for a home in India?</strong><small>Explore projects from Square Yards’ property data.</small></div><a class="btn btn-gold" href="/real-estate">DISCOVER REAL ESTATE　→</a></div></section>
  <section class="shell" id="how" style="padding-bottom:58px"><div class="section-head"><div class="eyebrow" style="justify-content:center">Simple, thoughtful support</div><h2>How it works</h2></div><div class="how-grid"><div class="how-item"><span class="step">01</span><div><strong>Choose a service</strong><p>Tell us what you need, from property to everyday essentials.</p></div></div><div class="how-item"><span class="step">02</span><div><strong>Explore trusted options</strong><p>Browse project information and compare your options.</p></div></div><div class="how-item"><span class="step">03</span><div><strong>We’re here to help</strong><p>Get personal support throughout your journey.</p></div></div></div></section>
  <section class="trust"><div class="shell"><div class="section-head"><div class="eyebrow" style="justify-content:center">Care you can count on</div><h2>Why NRI Ease?</h2></div><div class="trust-grid"><div class="trust-item"><strong>◉ &nbsp;Verified partners</strong><p>Thoughtfully selected service providers.</p></div><div class="trust-item"><strong>◇ &nbsp;Secure by design</strong><p>Your details and decisions matter.</p></div><div class="trust-item"><strong>◎ &nbsp;Personal concierge</strong><p>A real person when you need a hand.</p></div><div class="trust-item"><strong>↻ &nbsp;Here for the follow-through</strong><p>Support that stays with you.</p></div></div></div></section></main>${footer()}`;
}

function projectImage(project) {
  const raw = String(project.image || '');
  if (/^https:\/\//i.test(raw)) return esc(raw);
  if (/^[\w./-]+$/.test(raw) && !raw.includes('..')) return `https://static.squareyards.com/${raw.replace(/^\/+/, '')}`;
  return '';
}

function projectImageFromDetails(response) {
  const detail = response?.detail || response;
  const project = detail?.projectData || response?.projectData || {};
  const images = Array.isArray(project.images)
    ? project.images.map(image => typeof image === 'string' ? image : (image?.image || image?.url || image?.src || '')).find(Boolean)
    : '';
  return images || project.image || '';
}

function loadRecommendationImage(id) {
  const key = String(id);
  if (recommendationImageCache.has(key) || recommendationImageRequests.has(key)) return recommendationImageRequests.get(key) || Promise.resolve();
  const request = mcpCall('get_entity_details', { entity: 'project', id: key })
    .then(response => {
      const image = projectImageFromDetails(response);
      recommendationImageCache.set(key, image || '');
      projectDetailsCache.set(key, response);
    })
    .catch(() => recommendationImageCache.set(key, ''))
    .finally(() => {
      recommendationImageRequests.delete(key);
      if (state.recommendationMode && location.pathname.startsWith('/real-estate')) render();
    });
  recommendationImageRequests.set(key, request);
  return request;
}

function loadRecommendationImages(recommendations) {
  const queue = recommendations
    .map(item => String(item.project?.project_id ?? item.project?.id ?? ''))
    .filter(Boolean)
    .filter(id => !recommendationImageCache.has(id) && !recommendationImageRequests.has(id));
  const loadBatch = async () => {
    for (let index = 0; index < queue.length; index += 4) {
      await Promise.all(queue.slice(index, index + 4).map(loadRecommendationImage));
    }
  };
  if (queue.length) loadBatch();
}

function imageLoadFailed(image) {
  const parent = image?.parentElement;
  image?.remove();
  if (parent && !parent.querySelector('img')) parent.classList.add('image-unavailable');
}

function renderPartnerImage(id, response) {
  const box = document.querySelector(`[data-partner-image-id="${id}"]`);
  if (!box) return;
  const detail = response?.detail || response;
  const project = detail?.projectData || {};
  const firstImage = Array.isArray(project.images)
    ? project.images.map(image => typeof image === 'string' ? image : (image?.image || image?.url || image?.src || '')).find(Boolean)
    : '';
  const image = firstImage || project.image || '';
  const partner = partnerProjectFor(id);
  // This detail response was fetched for the exact Square Yards project ID,
  // so use its image directly instead of requiring a fragile filename/slug match.
  if (!partner || !image) {
    const placeholder = box.querySelector('.image-unavailable');
    if (placeholder) placeholder.setAttribute('aria-label', 'No project image was returned by Square Yards');
    return;
  }
  const financeMatch = INDORE_FINANCE_PROJECTS.find(item => item.id === String(id));
  const badge = financeMatch ? 'BANK REFERENCE FOUND' : 'PARTNER LISTING FOUND';
  box.innerHTML = `<img src="${projectImage({ image })}" alt="${esc(partner.name || 'Project')}" loading="lazy" onerror="imageLoadFailed(this)"><span class="badge">${badge}</span>`;
}

function loadPartnerProjectImages() {
  const boxes = [...app.querySelectorAll('[data-partner-image-id]')];
  if (!boxes.length) return;
  const load = box => {
    const id = box.dataset.partnerImageId;
    const cached = projectDetailsCache.get(id);
    if (cached) renderPartnerImage(id, cached);
    else loadProjectDetails(id).then(() => {
      const response = projectDetailsCache.get(id);
      if (response) renderPartnerImage(id, response);
      else document.querySelector(`[data-partner-image-id="${id}"] .image-unavailable`)?.setAttribute('aria-label', 'Project image unavailable');
    });
  };
  boxes.forEach(load);
}

function partnerProjectFor(id) {
  return INDORE_PARTNER_PROJECTS.find(item => String(item.id) === String(id));
}

function partnerSourceNames(partner) {
  return [...new Set(partner.links.map(link => {
    try {
      const hostname = new URL(link.url).hostname;
      return hostname.startsWith('www.') ? hostname.slice(4) : hostname;
    }
    catch { return ''; }
  }).filter(Boolean))];
}

function partnerSourceBrand(url) {
  let host = '';
  try { host = new URL(url).hostname.replace(/^www\./, ''); } catch {}
  if (host.includes('housing.com')) return { name: 'Housing.com', mark: 'H', theme: 'housing' };
  if (host.includes('totalrealtysolutions.org')) return { name: 'Total Realty', mark: 'TR', theme: 'total-realty' };
  if (host.includes('indoprops.com')) return { name: 'Indoprops', mark: 'IP', theme: 'indoprops' };
  if (host.includes('realestateindia.com')) return { name: 'RealEstateIndia', mark: 'RE', theme: 'realestate-india' };
  return { name: host || 'Property website', mark: '↗', theme: 'other' };
}

function partnerSourceGroups(partner) {
  const groups = new Map();
  partner.links.forEach(link => {
    const brand = partnerSourceBrand(link.url);
    if (!groups.has(brand.name)) groups.set(brand.name, { ...brand, links: [] });
    groups.get(brand.name).links.push(link);
  });
  return [...groups.values()];
}

function partnerProjectCard(partner) {
  const finance = INDORE_FINANCE_PROJECTS.find(item => item.id === String(partner.id));
  const bestLink = finance
    ? { url: finance.banks[0].url }
    : (partner.links.find(link => link.type === 'Unit listing') || partner.links[0]);
  const banks = finance?.banks.map(bank => bank.bank).join(' · ');
  const financeBadge = finance || partner.financeReference;
  return `<article class="property-card partner-property-card"><div class="property-image partner-property-image" data-partner-image-id="${esc(partner.id)}"><div class="image-unavailable" role="img" aria-label="Loading ${esc(partner.name)} project image"></div><span class="badge">${financeBadge ? 'BANK REFERENCE FOUND' : 'PARTNER LISTING FOUND'}</span></div><div class="property-info"><h3>${esc(partner.name)}</h3><p class="property-meta">Square Yards project ID: ${esc(partner.id)}</p><p class="property-meta">${esc(partner.locality)} · Indore</p>${partner.developer ? `<p class="property-meta">Builder: ${esc(partner.developer)}</p>` : ''}<p class="partner-availability">${esc(banks ? `Bank references: ${banks}` : partner.status)}</p><p class="partner-sites">${esc(partnerSourceNames(partner).join(' · '))}</p><div class="card-actions"><button class="btn btn-navy" onclick="openDetails('${esc(partner.id)}')">PROJECT DETAILS</button><a class="btn btn-gold" href="${esc(bestLink.url)}" target="_blank" rel="noopener noreferrer">${financeBadge ? 'VIEW SOURCE' : 'VIEW LISTING'}</a></div></div></article>`;
}

function indorePartnerSection() {
  return `<section class="partner-listings-section"><div class="eyebrow">Property and bank references</div><h2>Indore projects with external listings or finance references</h2><p class="partner-section-intro">Browse projects with a matching property-site listing or bank-published project reference. Open a source to check its current information.</p><div class="property-grid partner-property-grid">${INDORE_PARTNER_PROJECTS.map(partnerProjectCard).join('')}</div><p class="partner-section-note">A bank reference does not guarantee loan approval for a buyer or unit. Property-site listings can change; confirm availability with the source.</p></section>`;
}

function indoreFinanceCard(item) {
  const finance = item.banks.map(bank => `<div class="finance-bank-row"><span class="finance-bank-mark" aria-hidden="true">${esc(bank.bank.split(' ').map(word => word[0]).join('').slice(0, 3))}</span><div class="finance-bank-copy"><b>${esc(bank.bank)}</b><small>${esc(bank.status)}</small><span>Bank list: ${esc(bank.listed)}${bank.builder ? ` · Builder: ${esc(bank.builder)}` : ''}${bank.code ? ` · Code: ${esc(bank.code)}` : ''}</span></div><a href="${esc(bank.url)}" target="_blank" rel="noopener noreferrer" aria-label="Search ${esc(bank.bank)} source">SOURCE ↗</a></div>`).join('');
  const possible = (item.possibleBanks || []).map(bank => `<div class="finance-bank-row finance-bank-possible"><span class="finance-bank-mark" aria-hidden="true">${esc(bank.bank.split(' ').map(word => word[0]).join('').slice(0, 3))}</span><div class="finance-bank-copy"><b>${esc(bank.bank)} · Possible match</b><small>${esc(bank.status)}</small><span>Bank list: ${esc(bank.listed)}${bank.code ? ` · Code: ${esc(bank.code)}` : ''}</span></div><a href="${esc(bank.url)}" target="_blank" rel="noopener noreferrer" aria-label="Check ${esc(bank.bank)} source">CHECK ↗</a></div>`).join('');
  return `<article class="finance-project-card"><div class="finance-project-head"><div><h3>${esc(item.name)}</h3><small>Square Yards project ID: ${esc(item.id)}</small></div><button class="btn btn-navy" onclick="openDetails('${esc(item.id)}')">PROJECT DETAILS</button></div><div class="finance-bank-list">${finance}${possible}</div><div class="finance-project-foot"><span>Locality guideline trend</span><button class="finance-trend-link" onclick="openProjectTrend('${esc(item.id)}')">View trend ↗</button></div></article>`;
}

function cityFinanceSection(projectId = '') {
  const key = String(projectId);
  const result = financierCache.get(key);
  if (!result) {
    if (financierErrors.has(key)) {
      return `<section class="detail-section finance-section"><div class="eyebrow">Bank-published project lists</div><h2>Home finance references</h2><p>${esc(financierErrors.get(key))}</p><button class="btn btn-outline" onclick="loadFinancierReferences('${esc(key)}',true)">TRY AGAIN</button></section>`;
    }
    queueMicrotask(() => loadFinancierReferences(key));
    return `<section class="detail-section finance-section"><div class="eyebrow">Bank-published project lists</div><h2>Home finance references</h2><div class="developer-loading"><span class="loader"></span><p>Loading bank references for this project…</p></div></section>`;
  }
  const cards = result.finance_references.map(reference => {
    const bank = reference.financier_name || 'Financier';
    const initials = bank.split(' ').map(word => word[0]).join('').slice(0, 3);
    const status = reference.match_status === 'exact' ? 'Exact project match' : reference.match_status === 'possible' ? 'Possible project match · verify identity' : reference.match_status === 'unmatched' ? 'Unmatched bank listing' : 'Listed by financier';
    const url = reference.source_url ? `<a href="${esc(reference.source_url)}" target="_blank" rel="noopener noreferrer">SOURCE ↗</a>` : '';
    return `<div class="finance-bank-row ${reference.match_status === 'possible' || reference.match_status === 'unmatched' ? 'finance-bank-possible' : ''}"><span class="finance-bank-mark" aria-hidden="true">${esc(initials)}</span><div class="finance-bank-copy"><b>${esc(bank)}</b><small>${esc(status)}${reference.source_title ? ` · ${esc(reference.source_title)}` : ''}</small><span>Bank list: ${esc(reference.listed_project_name)}${reference.builder_name ? ` · Builder: ${esc(reference.builder_name)}` : ''}${reference.bank_project_code ? ` · Code: ${esc(reference.bank_project_code)}` : ''}${reference.match_note ? ` · ${esc(reference.match_note)}` : ''}</span></div>${url}</div>`;
  }).join('');
  return `<section class="detail-section finance-section"><div class="eyebrow">Bank-published project lists</div><h2>Home finance references</h2><p class="section-intro">Bank references linked to this project in our database. Open a source to review the listing. A project listing is not a loan approval or rate quote for an individual buyer.</p>${cards ? `<div class="finance-bank-list">${cards}</div>` : '<p>No bank-list match has been recorded for this project in our current database.</p>'}<p class="partner-section-note">Confirm the exact project phase, builder and unit with the financier. Approval remains subject to the financier’s current policy and the buyer’s eligibility.</p></section>`;
}

function loadFinancierReferences(projectId, retry = false) {
  const key = String(projectId);
  if (financierCache.has(key) || financierRequests.has(key)) return financierRequests.get(key);
  if (retry) financierErrors.delete(key);
  const request = ensureProjectRecord(key).then(saved => {
    if (!saved) throw new Error(projectRecordErrors.get(key) || 'Could not prepare this project for the finance lookup.');
    return fetch(`/api/financier-projects?project_id=${encodeURIComponent(key)}`, { headers: { Accept: 'application/json' } });
  })
    .then(async response => {
      const payload = await response.json();
      if (!response.ok || !payload?.ok) throw new Error(payload?.error || `Finance lookup failed (${response.status}).`);
      if (!Array.isArray(payload.finance_references)) throw new Error('The finance API response did not include finance_references.');
      financierCache.set(key, payload);
      financierErrors.delete(key);
    })
    .catch(error => financierErrors.set(key, error.message || 'Could not load financier references.'))
    .finally(() => {
      financierRequests.delete(key);
      if (location.pathname.startsWith(`/property/${key}`)) render();
    });
  financierRequests.set(key, request);
  return request;
}

function partnerDetailsSection(id) {
  const partner = partnerProjectFor(id);
  if (!partner) return '';
  const sourceCards = partnerSourceGroups(partner).map(source => `<article class="partner-source-card"><div class="partner-source-heading"><span class="partner-site-icon ${esc(source.theme)}" aria-label="${esc(source.name)} logo">${esc(source.mark)}</span><span><b>${esc(source.name)}</b><small>External property source · ${source.links.length} ${source.links.length === 1 ? 'link' : 'links'}</small></span></div><div class="partner-source-links">${source.links.map(link => `<a href="${esc(link.url)}" target="_blank" rel="noopener noreferrer"><span><b>${esc(link.label.split(' · ').slice(1).join(' · ') || link.label)}</b><small>${esc(link.type)}</small></span><strong>VIEW LISTING <span aria-hidden="true">↗</span></strong></a>`).join('')}</div></article>`).join('');
  return `<section class="detail-section partner-detail-section"><div class="eyebrow">Local property partners</div><h2>Where to enquire about this project</h2><p class="section-intro">Choose a website to view its project page or available listings. You’ll leave NRI Ease when you open a link.</p><div class="partner-listing-status"><span class="source-dot"></span><div><b>${esc(partner.status)}</b><small>${esc(partner.locality)} · Indore</small></div></div><div class="partner-source-grid">${sourceCards}</div><p class="partner-section-note">Listings and prices can change. Confirm current availability and project details with the provider.</p></section>`;
}

function trendPercent(current, previous) {
  return previous > 0 ? ((current / previous) - 1) * 100 : null;
}

function formatTrendPercent(value) {
  return value === null || !Number.isFinite(value) ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
}

const SQM_PER_SQFT = 10.7639;
function formatSqftRate(value) {
  const rate = Number(value) / SQM_PER_SQFT;
  return Number.isFinite(rate) ? `₹${rate.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—';
}

function loadPriceTrend(id, retry = false) {
  const key = String(id);
  if (priceTrendCache.has(key) || priceTrendRequests.has(key)) return priceTrendRequests.get(key);
  if (retry) priceTrendErrors.delete(key);
  const request = ensureProjectRecord(key).then(saved => {
    if (!saved) throw new Error(projectRecordErrors.get(key) || 'Could not prepare this project for the price-trends lookup.');
    return fetch(`/api/price-trends?project_id=${encodeURIComponent(key)}&rate_code=plot_residential_sqm`, { headers: { Accept: 'application/json' } });
  })
    .then(async response => {
      const payload = await response.json();
      if (response.status === 404 && /No (?:guideline rows matched|residential DLC rate history is stored)/i.test(payload?.error || '')) {
        priceTrendCache.set(key, { ...payload, points: [] });
        priceTrendErrors.delete(key);
        return;
      }
      if (!response.ok || !payload?.ok) throw new Error(payload?.error || `Price trend request failed (${response.status}).`);
      if (!Array.isArray(payload.points)) throw new Error('The price trend API response did not include a points array.');
      priceTrendCache.set(key, payload);
      priceTrendErrors.delete(key);
    })
    .catch(error => priceTrendErrors.set(key, error.message || 'Could not load locality guideline data.'))
    .finally(() => {
      priceTrendRequests.delete(key);
      if (location.pathname.startsWith(`/property/${key}`)) render();
    });
  priceTrendRequests.set(key, request);
  return request;
}

function cityAppreciationSection(id, projectName, city = '') {
  const key = String(id);
  const trend = priceTrendCache.get(key);
  const sourceLabel = trend?.source_label || (city ? `Official valuation schedule for ${city}` : 'Official locality valuation schedule');
  if (!trend) {
    if (priceTrendErrors.has(key)) {
      const error = priceTrendErrors.get(key);
      const retryButton = /rate-history tables are not set up/i.test(error) ? '' : `<button class="btn btn-outline" onclick="retryPriceTrend('${esc(key)}')">TRY AGAIN</button>`;
      return `<section id="property-appreciation" class="detail-section appreciation-section"><div class="eyebrow">${esc(sourceLabel)}</div><h2>Property appreciation trend</h2><p class="section-intro">${esc(projectName)} · locality-based residential plot guideline benchmark.</p><div class="appreciation-api-error"><p>${esc(error)}</p>${retryButton}</div><div class="appreciation-source"><span aria-hidden="true">i</span><p>This is a government guideline benchmark, not a transaction-price trend. A dated locality rate history is required to calculate a trend.</p></div></section>`;
    }
    queueMicrotask(() => loadPriceTrend(key));
    return `<section id="property-appreciation" class="detail-section appreciation-section"><div class="eyebrow">${esc(sourceLabel)}</div><h2>Property appreciation trend</h2><p class="section-intro">${esc(projectName)} · loading residential plot guideline rates for the project locality…</p><div class="appreciation-api-loading"><span class="loader"></span><span>Loading locality guideline rates from the API</span></div></section>`;
  }
  const points = trend.points.map(point => ({
    ...point,
    year: String(point.financial_year),
    average: Number(point.average_rate),
    minimum: Number(point.min_rate),
    maximum: Number(point.max_rate)
  })).filter(point => Number.isFinite(point.average) && Number.isFinite(point.maximum)).sort((a, b) => a.year.localeCompare(b.year));
  if (!points.length) return `<section id="property-appreciation" class="detail-section appreciation-section"><div class="eyebrow">${esc(sourceLabel)}</div><h2>Property appreciation trend</h2><p class="section-intro">${esc(trend.error || `No residential DLC rate history is currently stored for ${trend.locality || trend.project?.locality || projectName}.`)}</p><div class="appreciation-source"><span aria-hidden="true">i</span><p>A locality match-review row is not rate history. Dated rate values must be imported for this locality before a trend can be displayed.</p></div></section>`;
  const chartWidth = 720, chartHeight = 270, left = 76, right = 24, top = 18, bottom = 48;
  const innerWidth = chartWidth - left - right, innerHeight = chartHeight - top - bottom;
  const maxRate = Math.max(...points.map(point => point.maximum / SQM_PER_SQFT));
  const axisMax = Math.max(1, Math.ceil(maxRate / 1000) * 1000);
  const coords = field => points.map((point, index) => {
    const value = point[field] / SQM_PER_SQFT;
    return { x: points.length === 1 ? left + innerWidth / 2 : left + innerWidth * index / (points.length - 1), y: top + innerHeight * (1 - value / axisMax), value, point };
  });
  const avgPoints = coords('average'), maxPoints = coords('maximum');
  const grid = Array.from({ length: 5 }, (_, index) => {
    const value = axisMax * (4 - index) / 4;
    const y = top + innerHeight * index / 4;
    return `<line x1="${left}" y1="${y}" x2="${chartWidth - right}" y2="${y}" class="trend-gridline"/><text x="${left - 10}" y="${y + 4}" text-anchor="end" class="trend-axis-label">₹${value >= 1000 ? `${(value / 1000).toFixed(value % 1000 ? 1 : 0)}k` : Math.round(value)}</text>`;
  }).join('');
  const polyline = list => list.map(point => `${point.x},${point.y}`).join(' ');
  const yearLabels = points.map((point, index) => `<text x="${avgPoints[index].x}" y="${chartHeight - 15}" text-anchor="middle" class="trend-axis-label">${esc(point.year)}</text>`).join('');
  const averageMarkers = avgPoints.map(point => `<circle cx="${point.x}" cy="${point.y}" r="4.5" class="trend-marker"><title>FY ${esc(point.point.year)} average: ${formatSqftRate(point.point.average)} per sq. ft.; ${esc(point.point.matched_records)} records</title></circle>`).join('');
  const maximumMarkers = maxPoints.map(point => `<circle cx="${point.x}" cy="${point.y}" r="4" class="trend-max-marker"><title>FY ${esc(point.point.year)} maximum: ${formatSqftRate(point.point.maximum)} per sq. ft.</title></circle>`).join('');
  const averages = points.map(point => point.average);
  const latestYoy = averages.length > 1 ? trendPercent(averages.at(-1), averages.at(-2)) : null;
  const totalGrowth = averages.length > 1 ? trendPercent(averages.at(-1), averages[0]) : null;
  const spanYears = averages.length > 1 ? Number(points.at(-1).year.slice(0, 4)) - Number(points[0].year.slice(0, 4)) : 0;
  const cagr = spanYears > 0 && averages[0] > 0 ? (Math.pow(averages.at(-1) / averages[0], 1 / spanYears) - 1) * 100 : null;
  const historicalRows = points.map((point, index) => `<tr><th scope="row">FY ${esc(point.year)}</th><td>${formatSqftRate(point.average)} / sq. ft.</td><td>${formatSqftRate(point.maximum)} / sq. ft.</td><td>${index === 0 ? 'Base year' : formatTrendPercent(trendPercent(point.average, points[index - 1].average))}</td><td>${Number(point.matched_records).toLocaleString('en-IN')}</td></tr>`).join('');
  const firstYear = points[0].year, lastYear = points.at(-1).year;
  const previousAvailable = points.length > 1 ? `FY ${points.at(-2).year} to FY ${lastYear}` : 'Only one financial year returned';
  const sourceLinks = [...new Map(points.flatMap(point => point.sources || []).map(source => [source.url || source.name, source])).values()];
  const sources = sourceLinks.map(source => {
    const url = /^https:\/\//i.test(String(source.url || '')) ? source.url : '';
    return url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(source.name || 'Source PDF')} ↗</a>` : esc(source.name || 'Source PDF');
  }).join(' · ');
  return `<section id="property-appreciation" class="detail-section appreciation-section"><div class="eyebrow">${esc(sourceLabel)}</div><h2>Property appreciation trend</h2><p class="section-intro">${esc(trend.project?.locality || projectName)} · locality-based residential plot guideline rates, ${esc(firstYear)} to ${esc(lastYear)}.</p><div class="appreciation-chart-card"><div class="appreciation-chart-heading"><div><b>Collector Guideline rate</b><small>Residential plot · ₹ per sq. ft. (converted from API ₹/sq. m)</small></div><span class="appreciation-legend"><i></i> Average <i class="legend-max"></i> Maximum</span></div><div class="appreciation-chart-scroll"><svg class="appreciation-chart" viewBox="0 0 ${chartWidth} ${chartHeight}" role="img" aria-label="Average and maximum locality collector guideline rates for ${esc(trend.project?.locality || projectName)}">${grid}<polyline points="${polyline(avgPoints)}" class="trend-line"/><polyline points="${polyline(maxPoints)}" class="trend-line trend-line-max"/>${averageMarkers}${maximumMarkers}${yearLabels}</svg></div></div><div class="appreciation-metrics"><div><small>Latest available-period change</small><b>${formatTrendPercent(latestYoy)}</b><span>${esc(previousAvailable)}</span></div><div><small>Average rate total change</small><b>${formatTrendPercent(totalGrowth)}</b><span>${esc(firstYear)} to ${esc(lastYear)}</span></div><div><small>Average rate annualized change</small><b>${formatTrendPercent(cagr)}</b><span>${spanYears ? `${spanYears}-year CAGR across available endpoints` : 'Not enough years to calculate'}</span></div></div><div class="appreciation-table-wrap"><table class="appreciation-table"><caption>Rate history and year-over-year movement</caption><thead><tr><th scope="col">Year</th><th scope="col">Average guideline / sq. ft.</th><th scope="col">Maximum guideline / sq. ft.</th><th scope="col">Average rate change</th><th scope="col">Matched records</th></tr></thead><tbody>${historicalRows}</tbody></table></div><div class="appreciation-source"><span aria-hidden="true">i</span><p><b>How to read this:</b> the API aggregates ${esc(trend.aggregation || 'matching locality records')}. Values are converted from ₹/sq. m to ₹/sq. ft. by dividing by 10.7639. Rate changes compare adjacent available periods; missing periods are not estimated. These are government guideline benchmarks, not actual sale prices, asking prices, or apartment prices. ${esc(trend.data_note || '')}${sources ? `<br><b>Sources:</b> ${sources}` : ''}</p></div></section>`;
}

function retryPriceTrend(id) {
  priceTrendCache.delete(String(id));
  loadPriceTrend(id, true);
  render();
}

function projectCard(project, recommendation = null) {
  const id = esc(project.id);
  const name = esc(project.name || 'Project');
  const beds = Array.isArray(project.bhkConfigs) ? project.bhkConfigs.join(' · ') : 'BHK details not listed';
  const city = esc(project.city || state.city);
  const locality = esc(project.locality || project.location || 'Location not listed');
  const developer = esc(project.developerName || 'Developer not listed');
  const status = esc(project.status || 'Status not listed');
  const price = esc(project.priceText || (project.priceOnRequest ? 'Price on request' : 'Price not listed'));
  const partner = partnerProjectFor(project.id);
  const area = project.minSize && project.maxSize ? `${esc(project.minSize)}–${esc(project.maxSize)} sq.ft. ${esc(project.areaUnit || '')}` : '';
  const rank = Number(recommendation?.rank) || Number(recommendation?.recommendation_rank) || Number(recommendation?.position) || null;
  const badge = recommendation ? `HIGHLY RECOMMENDED · #${rank || '—'}` : partner ? 'PARTNER LISTING FOUND' : 'SQUARE YARDS DATA';
  return `<article class="property-card live-property-card"><div class="property-image">${projectImage(project) ? `<img src="${projectImage(project)}" alt="${name} project image" loading="lazy" onerror="imageLoadFailed(this)">` : '<div class="image-unavailable" role="img" aria-label="Project image unavailable"></div>'}<span class="badge">${badge}</span></div><div class="property-info"><h3>${name}</h3><p class="developer">${developer} · ${city}</p><p class="property-meta">${esc(locality)} · ${status}</p><p class="property-meta">${esc(beds)}${area ? ` · ${area}` : ''}</p><div class="price">${price}</div><div class="card-actions"><button class="btn btn-navy" onclick="openDetails('${id}')">VIEW DETAILS</button><button class="btn btn-gold" onclick="openModal('Enquire about ${name}')">ENQUIRE</button></div></div></article>`;
}

function formatFiltersSummary() {
  const parts = [state.city];
  if (state.bhk) parts.push(`${state.bhk.replace(',', ' / ')} BHK`);
  parts.push(`Up to ${money(state.maxBudget)}`);
  if (state.possessionStatus) parts.push(state.possessionStatus.replaceAll('_', ' '));
  if (state.completionYear) parts.push(`Completion ${state.completionYear}`);
  parts.push(state.buildingType === '1' ? 'Residential' : 'Commercial');
  return parts.map(esc).join(' · ');
}

function paginationMarkup() {
  const pages = Math.ceil(state.total / MAX_RESULTS);
  if (pages <= 1) return '';
  const start = ((state.page - 1) * MAX_RESULTS) + 1;
  const end = Math.min(state.page * MAX_RESULTS, state.total);
  return `<nav class="pagination live-pagination" aria-label="Project pages"><span class="pagination-summary">Showing ${start}–${end} of ${state.total}</span><button class="page" onclick="loadProjects(${state.page - 1})" ${state.page <= 1 ? 'disabled' : ''} aria-label="Previous page">‹ Previous</button><span class="page-number">Page ${state.page} of ${pages}</span><button class="page" onclick="loadProjects(${state.page + 1})" ${state.page >= pages ? 'disabled' : ''} aria-label="Next page">Next ›</button></nav>`;
}

function realEstate() {
  if (!state.recommendationMode && !state.loaded && !state.loading && !state.error) queueMicrotask(loadProjects);
  const recommendations = state.recommendationData?.properties || [];
  const visible = state.recommendationMode
    ? recommendations.map(item => {
      const id = String(item.project?.project_id ?? item.project?.id ?? '');
      const listed = state.projects.find(project => String(project.id) === id) || {};
      return { ...listed, ...item.project, id, name: item.project?.project_name || item.project?.name || listed.name, image: item.project?.image || listed.image || recommendationImageCache.get(id) || '', locality: item.project?.locality || listed.locality || 'Locality not listed', city: item.project?.city || listed.city || state.city, status: listed.status || 'Recommended from available evidence' };
    })
    : state.projects;
  const total = state.recommendationMode ? recommendations.length : state.total;
  const firstResult = state.total ? ((state.page - 1) * MAX_RESULTS) + 1 : 0;
  const lastResult = Math.min(state.page * MAX_RESULTS, state.total);
  const count = state.recommendationMode ? `${total} recommended ${state.city} projects` : state.total ? `Showing ${firstResult}–${lastResult} of ${state.total} projects` : `${visible.length} projects`;
  let resultContent;
  if (state.recommendationMode && state.recommendationLoading) {
    resultContent = `<div class="api-state loading-state"><span class="loader"></span><div><b>Finding highly recommended properties</b><p>Scoring ${esc(state.city)} projects from the latest API data…</p></div></div>`;
  } else if (state.recommendationMode && state.recommendationError) {
    resultContent = `<div class="api-state error-state"><b>Recommendations could not be loaded.</b><p>${esc(state.recommendationError)}</p><button class="btn btn-navy" onclick="loadRecommendations()">TRY AGAIN</button></div>`;
  } else if (state.recommendationMode && !visible.length) {
    resultContent = `<div class="api-state"><b>No evidence-ranked ${esc(state.city)} projects are available yet.</b><p>You can still browse live Square Yards listings for ${esc(state.city)}. Import project and evidence data to enable database-backed recommendations.</p><button class="btn btn-navy" onclick="toggleRecommendations()">BROWSE LIVE ${esc(state.city.toUpperCase())} PROJECTS</button></div>`;
  } else if (state.recommendationMode) {
    resultContent = `<div class="recommendation-intro"><b>Top ${esc(state.city)} properties by available evidence</b><span>Recommendations use the evidence currently available for each project.</span></div><div class="property-grid">${visible.map((project, index) => projectCard(project, { ...recommendations[index], rank: recommendations[index]?.rank || index + 1 })).join('')}</div>`;
    queueMicrotask(() => loadRecommendationImages(recommendations));
  } else if (state.loading) {
    resultContent = `<div class="api-state loading-state"><span class="loader"></span><div><b>Finding matching projects</b><p>Loading live project data from Square Yards…</p></div></div>`;
  } else if (state.error) {
    resultContent = `<div class="api-state error-state"><b>We couldn’t load projects right now.</b><p>${esc(state.error)}</p><button class="btn btn-navy" onclick="loadProjects()">TRY AGAIN</button></div>`;
  } else if (!visible.length) {
    resultContent = `<div class="api-state"><b>No projects matched these filters.</b><p>Try another completion year, possession status, or increase the maximum budget.</p></div>`;
  } else {
    resultContent = `<div class="property-grid">${visible.map(projectCard).join('')}</div>${paginationMarkup()}`;
  }

  return `${header('Services')}<main class="shell real-estate-page"><div class="crumb"><a href="/">Home</a><span>›</span> Services <span>›</span> <b>Real Estate</b></div>
    <div class="listing-title"><div><div class="eyebrow">Find your place in India</div><h1>Real estate, made more personal.</h1><p>Live project results from Square Yards, matched to your search.</p></div><span class="list-count">${esc(count)}</span></div>
    <section class="filters live-filters"><div class="filter-grid live-filter-grid">
      <div class="filter"><label for="city-filter">City</label><select id="city-filter" onchange="changeFilter('city',this.value)">${cityOptions(state.city)}</select></div>
      <div class="filter"><label for="bhk-filter">BHK</label><select id="bhk-filter" onchange="changeFilter('bhk',this.value)"><option value="">Any BHK</option><option value="1" ${state.bhk === '1' ? 'selected' : ''}>1 BHK</option><option value="2" ${state.bhk === '2' ? 'selected' : ''}>2 BHK</option><option value="3" ${state.bhk === '3' ? 'selected' : ''}>3 BHK</option><option value="4,5" ${state.bhk === '4,5' ? 'selected' : ''}>4+ BHK</option></select></div>
      <div class="filter"><label for="budget-filter">Maximum budget <span class="filter-value">${money(state.maxBudget)}</span></label><input id="budget-filter" type="range" min="5000000" max="50000000" step="1000000" value="${state.maxBudget}" oninput="updateBudget(this.value)"><div class="range-note"><span>₹50L</span><span>Up to ₹5Cr</span></div></div>
      <div class="filter"><label for="possession-filter">Possession</label><select id="possession-filter" onchange="changeFilter('possessionStatus',this.value)"><option value="">Any possession</option><option value="new_launch" ${state.possessionStatus === 'new_launch' ? 'selected' : ''}>New launch</option><option value="under_construction" ${state.possessionStatus === 'under_construction' ? 'selected' : ''}>Under construction</option><option value="ready_to_move" ${state.possessionStatus === 'ready_to_move' ? 'selected' : ''}>Ready to move</option></select></div>
      <div class="filter"><label for="year-filter">Completion year</label><select id="year-filter" onchange="changeFilter('completionYear',this.value)"><option value="">Any year</option>${Array.from({length: 11}, (_, i) => 2026 + i).map(year => `<option value="${year}" ${state.completionYear === String(year) ? 'selected' : ''}>${year}</option>`).join('')}</select></div>
      <div class="filter"><label for="building-filter">Property category</label><select id="building-filter" onchange="changeFilter('buildingType',this.value)"><option value="1" ${state.buildingType === '1' ? 'selected' : ''}>Residential</option><option value="2" ${state.buildingType === '2' ? 'selected' : ''}>Commercial</option></select></div>
    </div><div class="filter-bottom live-filter-bottom"><span>${state.recommendationMode ? `${esc(state.city)} · Ranked by property evidence` : formatFiltersSummary()}</span><div class="filter-controls"><button class="text-button" onclick="clearFilters()">Clear all</button><button class="btn ${state.recommendationMode ? 'btn-navy' : 'btn-outline'}" onclick="toggleRecommendations()">${state.recommendationMode ? 'BACK TO ALL PROJECTS' : 'HIGHLY RECOMMENDED'}</button><button class="btn btn-gold" onclick="loadProjects()" ${state.recommendationMode ? 'disabled' : ''}>APPLY FILTERS</button></div></div></section>
    <div class="data-source-note"><span class="source-dot"></span> Live project data from Square Yards · Showing up to ${MAX_RESULTS} projects per page. Partner and bank references appear on matching project cards. RERA numbers/status are not independently verified here.</div>
    <div class="results-layout live-results"><div class="live-results-main"><div class="results-count">${esc(count)}</div>${resultContent}</div><aside class="concierge-box"><div class="eyebrow">A personal touch</div><h3>Need a hand finding home?</h3><p>Tell us what matters to you. Our concierge can help you explore your options.</p><button class="btn btn-gold" onclick="openModal('Talk to a property concierge')">TALK TO A CONCIERGE</button><small>Friendly help, wherever you are.</small></aside></div>
    <p class="live-disclaimer">Listings, prices and project details are supplied by Square Yards and may change. Confirm current information with the developer and relevant state RERA authority before making a decision.</p>
  </main>${footer()}`;
}

function toggleRecommendations() {
  if (state.recommendationMode) {
    state.recommendationMode = false;
    state.recommendationError = '';
    render();
    return;
  }
  state.recommendationMode = true;
  loadRecommendations();
}

async function loadRecommendations() {
  if (!state.city || state.recommendationLoading) return;
  state.recommendationMode = true;
  state.recommendationLoading = true;
  state.recommendationError = '';
  render();
  try {
    const response = await fetch(`/api/top-properties?city=${encodeURIComponent(state.city)}&limit=20`, { headers: { Accept: 'application/json' } });
    const payload = await response.json();
    if (!response.ok || !payload?.ok || !Array.isArray(payload.properties)) {
      throw new Error(payload?.error || `Recommendation request failed (${response.status}).`);
    }
    state.recommendationData = payload;
  } catch (error) {
    state.recommendationError = error.message || 'Could not load recommended properties.';
  } finally {
    state.recommendationLoading = false;
    if (location.pathname.startsWith('/real-estate')) render();
  }
}

async function mcpCall(name, args) {
  const response = await fetch(SQUARE_YARDS_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/event-stream',
      'MCP-Protocol-Version': '2025-11-25'
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'tools/call',
      params: { name, arguments: args }
    })
  });
  const body = await response.text();
  if (!response.ok) throw new Error(`Square Yards returned HTTP ${response.status}.`);
  let payload;
  try {
    payload = JSON.parse(body);
  } catch {
    const dataLine = body.split(/\r?\n/).find(line => line.startsWith('data:'));
    if (!dataLine) throw new Error('The connector returned an unreadable response.');
    payload = JSON.parse(dataLine.slice(5).trim());
  }
  const result = payload.result || payload;
  if (result.isError) {
    const message = result.content?.map(item => item.text).filter(Boolean).join(' ');
    throw new Error(message || 'The connector could not complete this search.');
  }
  const structured = result.structuredContent || payload.structuredContent;
  if (!structured) {
    const message = result.content?.map(item => item.text).filter(Boolean).join(' ');
    throw new Error(message || 'No structured project data was returned.');
  }
  return structured;
}

async function loadProjects(page = 1) {
  state.page = Math.max(1, Number(page) || 1);
  const thisRequest = ++state.requestNumber;
  state.loading = true;
  state.error = '';
  render();
  const args = {
    location: state.city,
    maxPrice: Number(state.maxBudget),
    buildingType: state.buildingType,
    page: state.page,
    paging: MAX_RESULTS
  };
  if (state.bhk) args.bhk = state.bhk;
  if (state.possessionStatus) args.possessionStatus = state.possessionStatus;
  if (state.completionYear) args.possesion = state.completionYear;
  if (state.query.trim()) args.q = state.query.trim();
  try {
    const data = await mcpCall('search_projects', args);
    if (thisRequest !== state.requestNumber) return;
    state.projects = Array.isArray(data.projects) ? data.projects.slice(0, MAX_RESULTS) : [];
    state.total = Number(data.total ?? data.totalCount ?? data.count ?? state.projects.length);
    state.loaded = true;
    state.loading = false;
    state.error = '';
  } catch (error) {
    if (thisRequest !== state.requestNumber) return;
    state.loading = false;
    state.loaded = true;
    state.projects = [];
    state.total = 0;
    state.error = error instanceof TypeError
      ? 'The browser could not reach the Square Yards connector. Check your internet connection and try again.'
      : (error.message || 'Please try again.');
  }
  if (location.pathname.startsWith('/real-estate')) render();
}

function changeFilter(key, value) {
  state[key] = value;
  state.page = 1;
  if (state.recommendationMode) state.recommendationMode = false;
  const summary = document.querySelector('.live-filter-bottom > span');
  if (summary) summary.textContent = formatFiltersSummary();
  if (location.pathname.startsWith('/real-estate')) render();
}

function updateBudget(value) {
  state.maxBudget = Number(value);
  state.page = 1;
  if (state.recommendationMode) state.recommendationMode = false;
  const label = document.querySelector('.filter-value');
  if (label) label.textContent = money(state.maxBudget);
  const summary = document.querySelector('.live-filter-bottom > span');
  if (summary) summary.textContent = formatFiltersSummary();
}

function clearFilters() {
  state.city = CITIES[0] || '';
  state.bhk = '';
  state.maxBudget = 50000000;
  state.possessionStatus = '';
  state.completionYear = '';
  state.buildingType = '1';
  state.query = '';
  state.page = 1;
  state.error = '';
  state.loaded = false;
  state.recommendationMode = false;
  state.recommendationLoading = false;
  state.recommendationError = '';
  loadProjects();
}

function searchProperties() {
  state.city = CITIES.includes(document.getElementById('home-city')?.value) ? document.getElementById('home-city').value : (CITIES[0] || '');
  state.query = document.getElementById('home-search')?.value.trim() || '';
  state.page = 1;
  state.loaded = false;
  state.recommendationMode = false;
  state.recommendationLoading = false;
  state.recommendationError = '';
  history.pushState({}, '', '/real-estate');
  render();
  window.scrollTo(0, 0);
}

function asArray(value) {
  if (value == null || value === '') return [];
  return Array.isArray(value) ? value : [value];
}

function apiDate(value) {
  if (!value) return 'Not provided';
  const datePart = String(value).slice(0, 10);
  const date = new Date(`${datePart}T00:00:00Z`);
  return Number.isNaN(date.valueOf())
    ? esc(value)
    : new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date);
}

function plainText(value) {
  return String(value || '').replace(/<[^>]*>/g, ' ').replace(/&nbsp;/gi, ' ').replace(/&amp;/gi, '&').replace(/&quot;/gi, '"').replace(/&#39;/gi, "'").replace(/&lt;/gi, '<').replace(/&gt;/gi, '>').replace(/\s+/g, ' ').trim();
}

function parseMpReraDate(value) {
  const match = String(value || '').trim().match(/^(\d{2})-(\d{2})-(\d{4})$/);
  return match ? new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1])) : null;
}

async function loadMpReraRecord(registrationNumber, projectId) {
  const key = String(registrationNumber || '').trim().toUpperCase();
  if (!key || mpReraCache.has(key) || mpReraRequests.has(key)) return mpReraRequests.get(key);
  mpReraErrors.delete(key);
  const url = new URL(MP_RERA_SEARCH_ENDPOINT);
  url.searchParams.set('show', '20');
  url.searchParams.set('pagenum', '1');
  url.searchParams.set('search_txt', key);
  const request = fetch(url, { headers: { Accept: 'text/html' } })
    .then(response => {
      if (!response.ok) throw new Error(`MP RERA returned HTTP ${response.status}.`);
      return response.text();
    })
    .then(html => {
      const documentResult = new DOMParser().parseFromString(html, 'text/html');
      const rows = [...documentResult.querySelectorAll('#example tbody tr, table tbody tr')];
      const record = rows.map(row => {
        const cells = [...row.querySelectorAll('td')].map(cell => cell.textContent.replace(/\s+/g, ' ').trim());
        const detailAnchor = row.querySelector('a[href*="view_project_details.php"]');
        let detailUrl = '';
        if (detailAnchor) {
          const candidate = new URL(detailAnchor.getAttribute('href'), MP_RERA_ORIGIN);
          if (candidate.origin === MP_RERA_ORIGIN) detailUrl = candidate.href;
        }
        return { name: cells[1] || '', type: cells[2] || '', districtArea: cells[3] || '', number: cells[4] || '', validity: cells[5] || '', status: cells[6] || '', detailUrl };
      }).find(item => item.number.toUpperCase() === key && /\bindore\b/i.test(item.districtArea));
      mpReraCache.set(key, record || null);
    })
    .catch(error => mpReraErrors.set(key, error.message || 'MP RERA could not be reached from this browser.'))
    .finally(() => {
      mpReraRequests.delete(key);
      if (location.pathname.startsWith(`/property/${projectId}`)) render();
    });
  mpReraRequests.set(key, request);
  return request;
}

async function loadRajasthanReraRecord(registrationNumber, projectId) {
  const key = String(registrationNumber || '').trim().toUpperCase();
  if (!key || rajasthanReraCache.has(key) || rajasthanReraRequests.has(key)) return rajasthanReraRequests.get(key);
  rajasthanReraErrors.delete(key);
  const request = fetch('/api/rajasthan-rera', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({ RegistrationNo: registrationNumber })
  })
    .then(async response => {
      const payload = await response.json();
      if (!response.ok || payload?.ok === false) throw new Error(payload?.error || `Rajasthan RERA returned HTTP ${response.status}.`);
      const rows = Array.isArray(payload?.Data) ? payload.Data : [];
      const record = rows.find(item => String(item.REGISTRATIONNO || '').trim().toUpperCase() === key && /\bjaipur\b/i.test(item.DistrictName || '')) || null;
      rajasthanReraCache.set(key, record);
    })
    .catch(error => rajasthanReraErrors.set(key, error.message || 'Rajasthan RERA could not be reached.'))
    .finally(() => {
      rajasthanReraRequests.delete(key);
      if (location.pathname.startsWith(`/property/${projectId}`)) render();
    });
  rajasthanReraRequests.set(key, request);
  return request;
}

async function loadGujaratReraRecord(registrationNumber, projectId) {
  const key = String(registrationNumber || '').trim().toUpperCase();
  if (!key || gujaratReraCache.has(key) || gujaratReraRequests.has(key)) return gujaratReraRequests.get(key);
  gujaratReraErrors.delete(key);
  const request = fetch('/api/gujarat-rera', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({ RegistrationNo: registrationNumber })
  })
    .then(async response => {
      const payload = await response.json();
      if (!response.ok || payload?.ok === false) throw new Error(payload?.error || `Gujarat RERA returned HTTP ${response.status}.`);
      const rows = Array.isArray(payload?.data) ? payload.data : [];
      const record = rows.find(item => String(item.regNo || '').trim().toUpperCase() === key && String(item.entityType || '').trim().toUpperCase() === 'PROJECT') || null;
      gujaratReraCache.set(key, record);
    })
    .catch(error => gujaratReraErrors.set(key, error.message || 'Gujarat RERA could not be reached.'))
    .finally(() => {
      gujaratReraRequests.delete(key);
      if (location.pathname.startsWith(`/property/${projectId}`)) render();
    });
  gujaratReraRequests.set(key, request);
  return request;
}

function infrastructureRecordCard(record) {
  const source = record.source || {};
  const sourceLink = /^https?:\/\//i.test(source.url || '')
    ? `<a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">View source ↗</a>`
    : '';
  const location = record.area_name || (Array.isArray(record.locality_names) ? record.locality_names.join(', ') : '');
  return `<article class="infrastructure-record"><div class="infrastructure-record-head"><div><h3>${esc(record.project_name || 'Infrastructure project')}</h3><small>${esc([location, record.category, record.program_name].filter(Boolean).join(' · ') || 'Area not specified')}</small></div><span class="infrastructure-status">${esc(record.status_label || record.status_code || 'Status not stated')}</span></div>${record.description ? `<p>${esc(record.description)}</p>` : ''}<div class="infrastructure-record-source"><span>${esc([source.title, record.source_reference].filter(Boolean).join(' · ') || 'Source not specified')}</span>${sourceLink}</div></article>`;
}

function cityInfrastructureSection(projectId, city = '') {
  const data = infrastructureCache.get(String(projectId));
  const error = infrastructureErrors.get(String(projectId));
  const counts = data?.counts || {};
  const groups = [
    ['locality_matches', 'Projects naming this locality'],
    ['area_based_context', 'Area based context'],
    ['citywide_context', 'Citywide projects'],
    ['unlocated_proposals', 'Projects without a named area']
  ];
  const content = error
    ? `<div class="infrastructure-api-error"><p>${esc(error)}</p><button class="btn btn-outline" onclick="retryCityInfrastructure('${esc(projectId)}')">TRY AGAIN</button></div>`
    : !data
      ? '<div class="infrastructure-api-loading"><span class="loader"></span><span>Loading sourced infrastructure projects for this locality…</span></div>'
      : groups.map(([key, title]) => {
        const records = Array.isArray(data[key]) ? data[key] : [];
        if (!records.length) return '';
        return `<section class="infrastructure-group"><h3>${esc(title)} <span>${esc(counts[key] ?? records.length)}</span></h3>${records.map(infrastructureRecordCard).join('')}</section>`;
      }).join('') || '<p class="infrastructure-empty">No infrastructure records were returned for this project.</p>';
  const noLocalityMatch = data && Number(counts.locality_matches || 0) === 0
    ? '<p class="infrastructure-match-note">No source explicitly names this project’s locality. Area based, citywide, and unlocated records are shown separately and should not be read as nearby projects.</p>'
    : '';
  return `<section class="detail-section infrastructure-section"><div class="eyebrow">Locality context · ${esc(city)}</div><h2>Infrastructure projects</h2><p class="section-intro">Sourced plans and projects are matched against the property locality by named-area text. This is not a distance calculation.</p>${content}${noLocalityMatch}${data?.data_note ? `<p class="infrastructure-data-note">${esc(data.data_note)}</p>` : ''}</section>`;
}

async function loadCityInfrastructure(projectId) {
  const key = String(projectId);
  if (infrastructureCache.has(key)) return infrastructureCache.get(key);
  if (infrastructureRequests.has(key)) return infrastructureRequests.get(key);
  infrastructureErrors.delete(key);
  const request = ensureProjectRecord(key).then(saved => {
    if (!saved) throw new Error(projectRecordErrors.get(key) || 'Could not prepare this project for the infrastructure lookup.');
    return fetch(`/api/infrastructure-projects?project_id=${encodeURIComponent(key)}`, { headers: { Accept: 'application/json' } });
  }).then(async response => {
    const payload = await response.json();
    if (!response.ok || payload?.ok === false) throw new Error(payload?.error || `Infrastructure API returned HTTP ${response.status}.`);
    infrastructureCache.set(key, payload);
    return payload;
  }).catch(error => {
    infrastructureErrors.set(key, error.message || 'Could not load infrastructure project data.');
  }).finally(() => {
    infrastructureRequests.delete(key);
    if (location.pathname.startsWith(`/property/${key}`)) render();
  });
  infrastructureRequests.set(key, request);
  return request;
}

function retryCityInfrastructure(projectId) {
  infrastructureErrors.delete(String(projectId));
  loadCityInfrastructure(projectId);
  render();
}

function propertyDetails() {
  const rawId = decodeURIComponent(location.pathname.split('/').pop() || '');
  const id = rawId.split('-')[0];
  const cached = projectDetailsCache.get(id);
  const card = state.projects.find(item => String(item.id) === id);
  const detail = cached?.detail || cached;
  const project = detail?.projectData || {};
  const developerId = String(project.developerId || project.builderId || '');
  const developerResult = developerId ? developerDetailsCache.get(developerId) : null;
  const developerProfile = developerResult?.detail?.developerData || developerResult?.developerData || {};
  const name = project.projectName || detail?.name || card?.name || 'Project details';
  const city = project.city || card?.city || '';
  const locality = project.subLocation || card?.locality || card?.location || '';
  const region = project.location || card?.location || '';
  const isIndoreProject = /\bindore\b/i.test([city, region, locality].join(' '));
  const isJaipurProject = /\bjaipur\b/i.test([city, region, locality].join(' '));
  const isAhmedabadProject = /\bahmedabad\b/i.test([city, region, locality].join(' '));
  const status = project.status || card?.status || '';
  const price = project.priceText || card?.priceText || 'Price not listed';
  const beds = project.sizes || (card?.bhkConfigs || []).join(' · ') || 'Not listed';
  const reraData = asArray(project.projectReraData);
  const landmarksCandidate = detail?.landmarks;
  const landmarks = landmarksCandidate && Object.keys(landmarksCandidate).length ? landmarksCandidate : (project.landmarks || {});
  const landmarkEntries = Object.entries(landmarks).filter(([, entries]) => Array.isArray(entries) && entries.length);
  const unitRows = asArray(project.units);
  const amenityGroups = Object.entries(project.amenities || {}).filter(([, entries]) => Array.isArray(entries) && entries.length);
  const galleryImages = asArray(project.images).map(image => typeof image === 'string' ? image : (image?.image || image?.url || image?.src || '')).filter(Boolean);
  if (!galleryImages.length && card?.image) galleryImages.push(card.image);
  const gallery = galleryImages.length
    ? `<div class="gallery-track">${galleryImages.map((image, index) => `<img class="gallery-slide ${index === 0 ? 'is-active' : ''}" data-gallery-slide="${index}" src="${projectImage({ image })}" alt="${esc(name)} project image ${index + 1} of ${galleryImages.length}" ${index === 0 ? '' : 'hidden'} loading="lazy" onerror="imageLoadFailed(this)">`).join('')}</div>${galleryImages.length > 1 ? `<button class="gallery-arrow gallery-prev" aria-label="Previous project image" onclick="moveGallery(-1)">‹</button><button class="gallery-arrow gallery-next" aria-label="Next project image" onclick="moveGallery(1)">›</button><div class="gallery-pagination" aria-label="Project image navigation">${galleryImages.map((_, index) => `<button class="gallery-dot ${index === 0 ? 'is-active' : ''}" aria-label="Show image ${index + 1}" aria-current="${index === 0 ? 'true' : 'false'}" onclick="showGalleryImage(${index})"></button>`).join('')}</div><span class="gallery-count"><b data-gallery-current>1</b> / ${galleryImages.length}</span>` : ''}`
    : '<div class="image-unavailable" role="img" aria-label="Project image unavailable"></div>';

  const reraBlock = reraData.length
    ? reraData.map(row => `<article class="rera-record"><div class="rera-record-head"><div><small>Registered project / phase</small><h3>${esc(row.ReraProjectName || name)}</h3></div><div class="rera-number"><small>RERA registration number</small><b>${esc(row.ReraProjectNumber || 'Not provided')}</b></div></div><div class="rera-date-grid"><div><small>Launch date</small><b>${apiDate(row.LaunchDate)}</b></div><div><small>Registered completion date</small><b>${apiDate(row.CompletionDate)}</b></div></div></article>`).join('')
    : '<p>Square Yards did not include RERA registration details in this response.</p>';

  const mpReraNumbers = [...new Set(reraData.map(row => String(row.ReraProjectNumber || '').trim()).filter(Boolean))];
  const rajasthanReraNumbers = [...new Set(reraData.map(row => String(row.ReraProjectNumber || '').trim()).filter(Boolean))];
  const gujaratReraNumbers = [...new Set(reraData.map(row => String(row.ReraProjectNumber || '').trim()).filter(Boolean))];
  const mpReraVerification = isIndoreProject
    ? `<section class="detail-section mp-rera-section"><div class="eyebrow">Official state registry</div><h2>Madhya Pradesh RERA check</h2><p class="section-intro">We match the project’s registration number against the MP RERA public project register for Indore.</p>${mpReraNumbers.length ? mpReraNumbers.map(number => {
      const key = number.toUpperCase();
      const record = mpReraCache.get(key);
      const error = mpReraErrors.get(key);
      if (error) return `<article class="mp-rera-record mp-rera-error"><div><b>${esc(number)}</b><span>Could not check the MP RERA register from this browser.</span><small>${esc(error)}</small></div><button class="btn btn-outline" onclick="retryMpRera('${esc(number)}','${esc(id)}')">RETRY</button></article>`;
      if (record === null) return `<article class="mp-rera-record mp-rera-not-found"><div><span class="mp-rera-status">No matching Indore record found</span><b>${esc(number)}</b><small>No exact registration-number match in the MP RERA search response.</small></div></article>`;
      if (!record) return `<article class="mp-rera-record mp-rera-loading"><span class="loader"></span><div><b>${esc(number)}</b><span>Checking the MP RERA public register…</span></div></article>`;
      const validityParts = record.validity.split(/\s+to\s+/i);
      const validTo = parseMpReraDate(validityParts[1]);
      const validityCurrent = validTo ? validTo >= new Date(new Date().setHours(0, 0, 0, 0)) : null;
      const verifiedLabel = validityCurrent === true ? 'MP RERA VERIFIED' : 'MP RERA RECORD MATCHED';
      const validityNote = validityCurrent === false ? `<p class="mp-rera-validity-warning">Validity period ended ${esc(validityParts[1] || '')}. The authority status is shown above.</p>` : validityCurrent === null ? '<p class="mp-rera-validity-warning">Check the validity period on the official register.</p>' : '';
      return `<article class="mp-rera-record ${validityCurrent === true ? 'mp-rera-current' : validityCurrent === false ? 'mp-rera-expired' : 'mp-rera-unknown'}"><div class="mp-rera-record-top"><span class="mp-rera-status">${esc(verifiedLabel)}</span><b>${esc(record.number)}</b></div><div class="mp-rera-facts"><div><small>Official project name</small><b>${esc(record.name || 'Not listed')}</b></div><div><small>District / planning area</small><b>${esc(record.districtArea || 'Not listed')}</b></div><div><small>Validity shown by MP RERA</small><b>${esc(record.validity || 'Not listed')}</b></div><div><small>Authority status</small><b>${esc(record.status || 'Not listed')}</b></div></div>${validityNote}</article>`;
    }).join('') : '<p>Square Yards did not return an MP RERA registration number for this project, so an official lookup cannot be run.</p>'}<p class="mp-rera-note">“MP RERA verified” is shown when the registration number matches and the listed validity period is current. If a matching record’s validity has ended, the page shows “record matched” with an expiry notice instead.</p></section>`
    : '';

  const rajasthanReraVerification = isJaipurProject
    ? `<section class="detail-section mp-rera-section rajasthan-rera-section"><div class="eyebrow">Official state registry</div><h2>Rajasthan RERA check</h2><p class="section-intro">We check Jaipur project registration numbers against the Rajasthan RERA records.</p>${rajasthanReraNumbers.length ? rajasthanReraNumbers.map(number => {
      const key = number.toUpperCase();
      const record = rajasthanReraCache.get(key);
      const error = rajasthanReraErrors.get(key);
      if (error) return `<article class="mp-rera-record mp-rera-error"><div><b>${esc(number)}</b><span>Could not check the Rajasthan RERA register.</span><small>${esc(error)}</small></div><button class="btn btn-outline" onclick="retryRajasthanRera('${esc(number)}','${esc(id)}')">RETRY</button></article>`;
      if (record === null) return `<article class="mp-rera-record mp-rera-not-found"><div><span class="mp-rera-status">No matching Jaipur record found</span><b>${esc(number)}</b><small>The API returned no exact registration-number match for Jaipur.</small></div></article>`;
      if (!record) return `<article class="mp-rera-record mp-rera-loading"><span class="loader"></span><div><b>${esc(number)}</b><span>Checking Rajasthan RERA…</span></div></article>`;
      const approved = String(record.AppStatus || '').trim().toLowerCase() === 'application approved';
      return `<article class="mp-rera-record ${approved ? 'mp-rera-current' : 'mp-rera-unknown'}"><div class="mp-rera-record-top"><span class="mp-rera-status">${approved ? 'RAJASTHAN RERA VERIFIED' : 'RAJASTHAN RERA RECORD MATCHED'}</span><b>${esc(record.REGISTRATIONNO)}</b></div><div class="mp-rera-facts"><div><small>Official project name</small><b>${esc(record.ProjectName || 'Not listed')}</b></div><div><small>District</small><b>${esc(record.DistrictName || 'Not listed')}</b></div><div><small>Promoter</small><b>${esc(record.PromoterName || record.ORGNAME || 'Not listed')}</b></div><div><small>Application status</small><b>${esc(record.AppStatus || 'Not listed')}</b></div><div><small>Approved on</small><b>${apiDate(record.APPROVEDON)}</b></div><div><small>Revised completion date</small><b>${esc(record.RevisedDateOfComplation || 'Not listed')}</b></div><div><small>Certificate number</small><b>${esc(record.CertificateNo || 'Not listed')}</b></div></div></article>`;
    }).join('') : '<p>Square Yards did not return a Rajasthan RERA registration number for this project.</p>'}<p class="mp-rera-note">A green check is shown for an exact registration-number and Jaipur district match when Rajasthan RERA reports “Application Approved.”</p></section>`
      : '';

  const gujaratReraVerification = isAhmedabadProject
    ? `<section class="detail-section mp-rera-section gujarat-rera-section"><div class="eyebrow">Official state registry</div><h2>Gujarat RERA check</h2><p class="section-intro">We search the Gujarat RERA public registry using each registration number for Ahmedabad projects.</p>${gujaratReraNumbers.length ? gujaratReraNumbers.map(number => {
      const key = number.toUpperCase();
      const record = gujaratReraCache.get(key);
      const error = gujaratReraErrors.get(key);
      if (error) return `<article class="mp-rera-record mp-rera-error"><div><b>${esc(number)}</b><span>Could not check the Gujarat RERA register.</span><small>${esc(error)}</small></div><button class="btn btn-outline" onclick="retryGujaratRera('${esc(number)}','${esc(id)}')">RETRY</button></article>`;
      if (record === null) return `<article class="mp-rera-record mp-rera-not-found"><div><span class="mp-rera-status">No matching Gujarat RERA project found</span><b>${esc(number)}</b><small>The API returned no exact registration-number and PROJECT match.</small></div></article>`;
      if (!record) return `<article class="mp-rera-record mp-rera-loading"><span class="loader"></span><div><b>${esc(number)}</b><span>Checking Gujarat RERA…</span></div></article>`;
      return `<article class="mp-rera-record mp-rera-current"><div class="mp-rera-record-top"><span class="mp-rera-status">GUJARAT RERA VERIFIED</span><b>${esc(record.regNo)}</b></div><div class="mp-rera-facts"><div><small>Official project name</small><b>${esc(record.entityName || 'Not listed')}</b></div><div><small>District / taluka</small><b>${esc([record.distName, record.taluka].filter(Boolean).join(' · ') || 'Not listed')}</b></div><div><small>Property type</small><b>${esc(record.ptype || 'Not listed')}</b></div><div><small>PIN code</small><b>${esc(record.pinCode || 'Not listed')}</b></div><div><small>Registered dates</small><b>${esc(record.pdate || 'Not listed')}</b></div></div></article>`;
    }).join('') : '<p>Square Yards did not return a Gujarat RERA registration number for this project.</p>'}<p class="mp-rera-note">A green check means Gujarat RERA returned an exact registration-number match with entity type PROJECT. Project details above are from the state registry response.</p></section>`
    : '';

  const landmarksBlock = landmarkEntries.length
    ? `<div class="landmark-grid">${landmarkEntries.map(([category, entries], index) => {
      const nearest = [...entries].sort((a, b) => Number(a.km) - Number(b.km)).slice(0, 5);
      return `<details class="landmark-category" ${index < 4 ? 'open' : ''}><summary>${esc(category)} <span>${entries.length} nearby</span></summary><ul>${nearest.map(item => `<li><span><b>${esc(item.name || 'Landmark')}</b><small>${esc(item.area || locality || '')}</small></span><strong>${Number.isFinite(Number(item.km)) ? `${Number(item.km).toFixed(2)} km` : 'Distance n/a'}</strong></li>`).join('')}</ul></details>`;
    }).join('')}</div>`
    : '<p>No nearby landmark data was included in this response.</p>';

  const unitsBlock = unitRows.length
    ? `<div class="unit-grid">${unitRows.map(unit => `<article class="unit-card">${unit.image ? `<img src="${projectImage({ image: unit.image })}" alt="${esc(unit.name || unit.config || 'Unit')}" loading="lazy" onerror="imageLoadFailed(this)">` : ''}<div><b>${esc(unit.config || unit.category || unit.name || 'Unit')}</b><span>${esc(unit.area || unit.sizeText || 'Area not listed')}</span><strong>${esc(unit.price || unit.priceText || 'Price on request')}</strong></div></article>`).join('')}</div>`
    : '<p>Unit configurations and prices were not included in this response.</p>';

  const amenitiesBlock = amenityGroups.length
    ? `<div class="amenity-groups">${amenityGroups.map(([category, items]) => `<div class="amenity-group"><b>${esc(category)}</b><div>${items.map(item => `<span>${esc(item)}</span>`).join('')}</div></div>`).join('')}</div>`
    : '<p>Amenities were not included in this response.</p>';

  const cityStatus = Object.entries(developerProfile.projectsByCityAndStatus || {});
  const developerProjects = asArray(developerProfile.topProjects).filter(item => String(item.id) !== id);
  const developerProjectsBlock = developerProjects.length
    ? `<div class="developer-project-grid">${developerProjects.map(item => `<button class="developer-project-card" onclick="openDetails('${esc(item.id)}')">${item.image ? `<img src="${projectImage({ image: item.image })}" alt="${esc(item.name)}" loading="lazy" onerror="imageLoadFailed(this)">` : ''}<span class="developer-project-info"><b>${esc(item.name || 'Project')}</b><small>${esc([item.location, item.city].filter(Boolean).join(' · '))}</small><small>${esc(item.status || 'Status not listed')} · ${esc(item.sizes || 'Unit types not listed')}</small><strong>${esc(item.price || 'Price not listed')}</strong></span></button>`).join('')}</div>`
    : '<p>No other projects were listed in this developer profile.</p>';
  const developerSummary = developerResult
    ? `<section class="detail-section developer-profile-section"><div class="eyebrow">Builder profile</div><h2>Meet the developer</h2><article class="developer-profile-card"><div class="developer-profile-header">${developerProfile.image ? `<img class="developer-logo" src="${projectImage({ image: developerProfile.image })}" alt="${esc(developerProfile.name || project.developerName || 'Developer')} logo" onerror="this.remove()">` : '<span class="developer-logo-fallback" aria-hidden="true">⌂</span>'}<div><h3>${esc(developerProfile.name || project.developerName || card?.developerName || 'Developer')}</h3><p>Developer profile supplied by Square Yards</p></div><span class="developer-source-badge">SQUARE YARDS</span></div><div class="developer-facts"><div><small>Projects listed</small><b>${esc(developerProfile.totalProjects ?? developerProjects.length)}</b></div><div><small>Experience listed</small><b>${Number(developerProfile.experience) > 0 ? `${esc(developerProfile.experience)} years` : 'Not provided'}</b></div>${developerProfile.grade ? `<div><small>Square Yards profile grade</small><b>${esc(developerProfile.grade)}</b></div>` : ''}</div>${cityStatus.length ? `<div class="developer-city-status"><h4>Portfolio by city and status</h4><div>${cityStatus.map(([cityName, statuses]) => `<div><b>${esc(cityName)}</b><span>${Object.entries(statuses || {}).map(([projectStatus, count]) => `${esc(projectStatus)}: ${esc(count)}`).join(' · ')}</span></div>`).join('')}</div></div>` : ''}<p class="developer-profile-note">Portfolio counts, project statuses and any grade are provided by Square Yards. They are not an independent assessment or confirmation of completed delivery.</p></article><h3 class="developer-project-heading">Other projects listed for this developer</h3>${developerProjectsBlock}</section>`
    : developerId && developerErrors.has(developerId)
      ? `<section class="detail-section developer-profile-section"><div class="eyebrow">Builder profile</div><h2>Developer details</h2><p>Square Yards could not load this developer profile: ${esc(developerErrors.get(developerId))}</p><button class="btn btn-outline" onclick="loadDeveloperDetails('${esc(id)}','${esc(developerId)}')">TRY AGAIN</button></section>`
      : developerId
        ? '<section class="detail-section developer-profile-section"><div class="eyebrow">Builder profile</div><h2>Developer details</h2><div class="developer-loading"><span class="loader"></span><p>Loading the developer profile from Square Yards…</p></div></section>'
        : '<section class="detail-section developer-profile-section"><div class="eyebrow">Builder profile</div><h2>Developer details</h2><p>This project response did not include a developer ID, so a developer profile could not be matched safely.</p></section>';

  const description = plainText(project.description);
  const hasSupportedCity = Boolean(city || card?.city || state.city);
  const displayCity = city || card?.city || state.city;
  const appreciationSection = hasSupportedCity ? `${cityAppreciationSection(id, name, displayCity)}${cityFinanceSection(id)}` : '';
  const infrastructureSection = hasSupportedCity ? cityInfrastructureSection(id, displayCity) : '';
  const detailsContent = cached
    ? `${appreciationSection}${infrastructureSection}<section class="detail-section live-project-overview"><div class="eyebrow">Project snapshot</div><h2>Key details for your decision</h2><div class="live-detail-grid"><div><small>Location</small><b>${esc([locality, region, city].filter(Boolean).join(', ') || 'Not listed')}</b></div><div><small>Construction status</small><b>${esc(status || 'Not listed')}${project.projectStatusPer ? ` · ${esc(project.projectStatusPer)} complete` : ''}</b></div><div><small>Expected possession</small><b>${esc(project.possessionStartingFrom || 'Not listed')}</b></div><div><small>Configurations</small><b>${esc(beds)}</b></div><div><small>Project size</small><b>${project.projectArea ? `${esc(project.projectArea)} acres` : 'Not listed'}</b></div><div><small>Total units</small><b>${esc(project.totalUnits || card?.totalUnits || 'Not listed')}</b></div><div><small>Area range</small><b>${project.minSize && project.maxSize ? `${esc(project.minSize)}–${esc(project.maxSize)} sq.ft. (${esc(project.unitMinCatName || project.areaUnit || 'area')})` : 'See unit options below'}</b></div><div><small>Indicative price range</small><b>${esc(price)}</b></div></div>${description ? `<details class="project-description"><summary>Read project description</summary><p>${esc(description.slice(0, 1800))}${description.length > 1800 ? '…' : ''}</p></details>` : ''}</section>
      <section class="detail-section live-rera-section"><div class="eyebrow">Registration information</div><h2>RERA project records</h2>${reraBlock}<p class="live-disclaimer">These RERA details are supplied by Square Yards and have not been independently checked against the state authority’s register. Match the registration number, project/phase name, promoter and dates on the official RERA site.</p></section>
      ${mpReraVerification}
      ${rajasthanReraVerification}
      ${gujaratReraVerification}
      ${developerSummary}
      <section class="detail-section"><div class="eyebrow">Layouts and pricing</div><h2>Available unit options</h2>${unitsBlock}</section>
      <section class="detail-section"><div class="eyebrow">Around the project</div><h2>Nearby landmarks</h2><p class="section-intro">Distances and area labels shown here come from the project detail response.</p>${landmarksBlock}</section>
      <section class="detail-section"><div class="eyebrow">Facilities</div><h2>Amenities</h2>${amenitiesBlock}</section>`
    : state.error
      ? `<div class="api-state error-state"><b>Project details could not be loaded.</b><p>${esc(state.error)}</p><button class="btn btn-navy" onclick="loadProjectDetails('${esc(id)}')">TRY AGAIN</button></div>`
      : `<div class="api-state loading-state"><span class="loader"></span><div><b>Loading project details</b><p>Fetching project, RERA and nearby landmark details from Square Yards…</p></div></div>`;

  if (!cached && !detailRequests.has(id)) queueMicrotask(() => loadProjectDetails(id));
  if (cached && !projectRecordCache.has(id) && !projectRecordRequests.has(id) && !projectRecordErrors.has(id)) queueMicrotask(() => ensureProjectRecord(id));
  if (cached && hasSupportedCity && !infrastructureCache.has(id) && !infrastructureRequests.has(id) && !infrastructureErrors.has(id)) queueMicrotask(() => loadCityInfrastructure(id));
  if (cached && developerId && !developerDetailsCache.has(developerId) && !developerRequests.has(developerId) && !developerErrors.has(developerId)) queueMicrotask(() => loadDeveloperDetails(id, developerId));
  if (cached && isIndoreProject) mpReraNumbers.forEach(number => { if (!mpReraCache.has(number.toUpperCase()) && !mpReraRequests.has(number.toUpperCase()) && !mpReraErrors.has(number.toUpperCase())) queueMicrotask(() => loadMpReraRecord(number, id)); });
  if (cached && isJaipurProject) rajasthanReraNumbers.forEach(number => { if (!rajasthanReraCache.has(number.toUpperCase()) && !rajasthanReraRequests.has(number.toUpperCase()) && !rajasthanReraErrors.has(number.toUpperCase())) queueMicrotask(() => loadRajasthanReraRecord(number, id)); });
  if (cached && isAhmedabadProject) gujaratReraNumbers.forEach(number => { if (!gujaratReraCache.has(number.toUpperCase()) && !gujaratReraRequests.has(number.toUpperCase()) && !gujaratReraErrors.has(number.toUpperCase())) queueMicrotask(() => loadGujaratReraRecord(number, id)); });
  return `${header('Services')}<main class="shell detail-page"><div class="crumb"><a href="/">Home</a><span>›</span><a href="/real-estate">Real Estate</a><span>›</span><b>${esc(name)}</b></div><button class="back-link" onclick="history.pushState({},'', '/real-estate');render();window.scrollTo(0,0)">← &nbsp; BACK TO PROJECTS</button><section class="detail-hero live-detail-hero"><div class="detail-photo live-detail-gallery ${galleryImages.length === 1 ? 'gallery-single' : ''}">${gallery}<span class="badge">SQUARE YARDS PROJECT IMAGES</span></div><div class="detail-summary"><div class="eyebrow">${esc([city || card?.city, locality].filter(Boolean).join(' · ') || state.city)}</div><h1>${esc(name)}</h1><p class="detail-developer">by ${esc(project.developerName || card?.developerName || 'Developer not listed')}</p><div class="detail-price">${esc(price)}<small>Pricing supplied by Square Yards · confirm with developer</small></div><div class="detail-stats"><div><b>${esc(beds)}</b><small>Configurations</small></div><div><b>${esc(status || 'Not listed')}</b><small>Project status</small></div><div><b>${esc(project.possessionStartingFrom || 'Not listed')}</b><small>Expected possession</small></div></div><button class="btn btn-gold" onclick="openModal('Enquire about ${esc(name)}')">ASK ABOUT THIS PROJECT</button><p class="detail-note">Project and RERA information below is shown as supplied by Square Yards.</p></div></section><div class="detail-columns"><div>${detailsContent}</div><aside class="detail-sidebar"><div class="concierge-box"><div class="eyebrow">Here to help</div><h3>Want help reviewing this project?</h3><p>Ask our property concierge about registration documents, current pricing or the next steps.</p><button class="btn btn-gold" onclick="openModal('Enquire about ${esc(name)}')">SEND AN ENQUIRY</button><small>Your details stay in this demo.</small></div></aside></div></main>${footer()}`;
}

function showGalleryImage(index) {
  const slides = [...document.querySelectorAll('[data-gallery-slide]')];
  if (!slides.length) return;
  const next = (index + slides.length) % slides.length;
  slides.forEach((slide, i) => {
    slide.hidden = i !== next;
    slide.classList.toggle('is-active', i === next);
  });
  document.querySelectorAll('.gallery-dot').forEach((dot, i) => {
    dot.classList.toggle('is-active', i === next);
    dot.setAttribute('aria-current', i === next ? 'true' : 'false');
  });
  const counter = document.querySelector('[data-gallery-current]');
  if (counter) counter.textContent = String(next + 1);
}

function moveGallery(offset) {
  const active = document.querySelector('.gallery-slide.is-active');
  const current = Number(active?.dataset.gallerySlide || 0);
  showGalleryImage(current + offset);
}

async function loadProjectDetails(id) {
  if (detailRequests.has(id)) return detailRequests.get(id);
  const request = mcpCall('get_entity_details', { entity: 'project', id: String(id) })
    .then(data => {
      projectDetailsCache.set(id, data);
      state.error = '';
      return ensureProjectRecord(id);
    })
    .catch(error => {
      state.error = error.message || 'Please try again.';
    })
    .finally(() => {
      detailRequests.delete(id);
      if (location.pathname.startsWith(`/property/${id}`)) render();
    });
  detailRequests.set(id, request);
  return request;
}

async function ensureProjectRecord(id, retry = false) {
  const key = String(id);
  if (projectRecordCache.has(key)) return projectRecordCache.get(key);
  if (projectRecordRequests.has(key)) return projectRecordRequests.get(key);
  if (retry) projectRecordErrors.delete(key);
  const cached = projectDetailsCache.get(key);
  const detail = cached?.detail || cached || {};
  const project = detail.projectData || cached?.projectData || {};
  const card = state.projects.find(item => String(item.id) === key) || {};
  const name = project.projectName || project.name || detail.name || card.name;
  const city = project.city || detail.city || card.city || state.city;
  const locality = project.subLocation || project.locality || card.locality || (project.location && project.location !== city ? project.location : card.location) || '';
  if (!name || !city) {
    projectRecordErrors.set(key, 'Square Yards did not return a project name and city to save.');
    return Promise.resolve();
  }
  const request = fetch('/api/ensure-project', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ project_id: key, project_name: name, city, locality })
  })
    .then(async response => {
      const payload = await response.json();
      if (!response.ok || !payload?.ok) throw new Error(payload?.error || `Project lookup failed (${response.status}).`);
      projectRecordCache.set(key, payload);
      projectRecordErrors.delete(key);
      return payload;
    })
    .catch(error => {
      projectRecordErrors.set(key, error.message || 'Could not check the project table.');
    })
    .finally(() => {
      projectRecordRequests.delete(key);
      if (location.pathname.startsWith(`/property/${key}`)) render();
    });
  projectRecordRequests.set(key, request);
  return request;
}

async function loadDeveloperDetails(projectId, developerId) {
  const key = String(developerId);
  if (developerRequests.has(key)) return developerRequests.get(key);
  developerErrors.delete(key);
  const request = mcpCall('get_entity_details', { entity: 'developer', id: key })
    .then(data => {
      if (!data?.detail?.developerData && !data?.developerData) throw new Error('No developer profile details were returned.');
      developerDetailsCache.set(key, data);
    })
    .catch(error => {
      developerErrors.set(key, error.message || 'Please try again.');
    })
    .finally(() => {
      developerRequests.delete(key);
      if (location.pathname.startsWith(`/property/${projectId}`)) render();
    });
  developerRequests.set(key, request);
  return request;
}

function retryMpRera(registrationNumber, projectId) {
  const key = String(registrationNumber || '').trim().toUpperCase();
  mpReraCache.delete(key);
  mpReraErrors.delete(key);
  loadMpReraRecord(key, projectId);
  render();
}

function retryRajasthanRera(registrationNumber, projectId) {
  const key = String(registrationNumber || '').trim().toUpperCase();
  rajasthanReraCache.delete(key);
  rajasthanReraErrors.delete(key);
  loadRajasthanReraRecord(registrationNumber, projectId);
  render();
}

function retryGujaratRera(registrationNumber, projectId) {
  const key = String(registrationNumber || '').trim().toUpperCase();
  gujaratReraCache.delete(key);
  gujaratReraErrors.delete(key);
  loadGujaratReraRecord(registrationNumber, projectId);
  render();
}

function render() {
  app.innerHTML = location.pathname.startsWith('/property/')
    ? propertyDetails()
    : location.pathname.startsWith('/real-estate')
      ? realEstate()
      : home();
  if (location.pathname.startsWith('/real-estate') && state.city === 'Indore') requestAnimationFrame(loadPartnerProjectImages);
}

function openDetails(id) {
  history.pushState({}, '', `/property/${encodeURIComponent(id)}`);
  state.error = '';
  render();
  window.scrollTo(0, 0);
}

function openProjectTrend(id) {
  history.pushState({}, '', `/property/${encodeURIComponent(id)}#property-appreciation`);
  state.error = '';
  render();
  requestAnimationFrame(() => document.getElementById('property-appreciation')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
}

function openModal(title) {
  document.body.insertAdjacentHTML('beforeend', `<div class="modal-backdrop" onclick="if(event.target===this)this.remove()"><form class="modal" onsubmit="submitEnquiry(event)"><div class="eyebrow">We’re here for you</div><h2>${esc(title)}</h2><p>Share a few details and our concierge will be in touch. (Demo form — no information is sent.)</p><label>Your name</label><input required placeholder="Name"><label>Email address</label><input type="email" required placeholder="you@example.com"><label>How can we help?</label><textarea placeholder="Tell us a little about what you need"></textarea><div class="modal-actions"><button class="btn btn-outline" type="button" onclick="this.closest('.modal-backdrop').remove()">CANCEL</button><button class="btn btn-gold">SEND ENQUIRY</button></div></form></div>`);
}

function submitEnquiry(event) {
  event.preventDefault();
  const form = event.currentTarget;
  form.classList.add('success-state');
  form.innerHTML = `<div class="success-mark">✓</div><div class="eyebrow" style="justify-content:center">MESSAGE NOTED</div><h2>Thanks, your enquiry is ready.</h2><p>This is a frontend demo, so nothing has been sent or stored.</p><button type="button" class="btn btn-navy" onclick="this.closest('.modal-backdrop').remove()">DONE</button>`;
}

function toast(message) {
  document.querySelector('.toast')?.remove();
  document.body.insertAdjacentHTML('beforeend', `<div class="toast">${esc(message)}</div>`);
  setTimeout(() => document.querySelector('.toast')?.remove(), 2800);
}

window.addEventListener('popstate', render);

async function initializeCitiesAndRender() {
  try {
    const response = await fetch('/api/cities', { headers: { Accept: 'application/json' } });
    const payload = await response.json();
    if (!response.ok || !payload?.ok || !Array.isArray(payload.cities)) {
      throw new Error(payload?.error || `Could not load cities (${response.status}).`);
    }
    CITIES = [...new Set(payload.cities.map(city => String(city || '').trim()).filter(Boolean))];
    if (!CITIES.length) CITIES = [...FALLBACK_CITIES];
    if (!CITIES.includes(state.city)) state.city = CITIES[0];
  } catch (error) {
    // Live listings are fetched directly from Square Yards and remain useful
    // while the local projects table is empty or unavailable.
    CITIES = [...FALLBACK_CITIES];
    if (!CITIES.includes(state.city)) state.city = CITIES[0];
  }
  render();
}

initializeCitiesAndRender();
