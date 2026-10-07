/**
 * Royal Mail Click & Drop API v1 client
 *
 * Base URL:  https://api.parcel.royalmail.com/api/v1
 * Docs:      https://developer.royalmail.net/click-and-drop
 * Auth:      Authorization: Bearer {api_key}
 *            Get your API key from: Click & Drop > Settings > API credentials
 *
 * Note: This API creates orders in Click & Drop, which then generates labels.
 *       Labels are returned as PDF binary. Base64-encoded in this client.
 */

const BASE_URL = process.env.RM_BASE_URL || 'https://api.parcel.royalmail.com/api/v1';

// ─── Service codes ────────────────────────────────────────────────────────────
// These are the Service Register codes as they appear in Click & Drop
// (Settings → Shipping services). Raw codes are also accepted: pass either a
// friendly key below OR the bare code (e.g. 'OLP1') to createOrder.
export const RM_SERVICES = {
  // ─── Royal Mail UK: 1st & 2nd Class ────────────────────────────────────────
  'first-class':              'OLP1',
  'first-class-signed':       'OLP1SF',
  'second-class':             'OLP2',
  'second-class-signed':      'OLP2SF',

  // ─── Royal Mail UK: Tracked ───────────────────────────────────────────────
  'tracked-24':               'TOLP24',
  'tracked-24-signed':        'TOLP24SF',
  'tracked-24-age':           'TOLP24SFA',
  'tracked-48':               'TOLP48',
  'tracked-48-signed':        'TOLP48SF',
  'tracked-48-age':           'TOLP48SFA',

  // ─── Royal Mail UK: Special Delivery by 1pm ───────────────────────────────
  // Compensation tier is encoded in the service code itself.
  'special-delivery-750':     'SD1OLP',
  'special-delivery-1000':    'SD2OLP',
  'special-delivery-2500':    'SD3OLP',

  // ─── Parcelforce UK express ────────────────────────────────────────────────
  // Compensation tiers (Comp 1/2/3) are selected at booking via declared value.
  'parcelforce-10':              'PFE10',
  'parcelforce-10-signed':       'PFE10SF',
  'parcelforce-24':              'PFE24',
  'parcelforce-24-signed':       'PFE24SF',
  'parcelforce-48':              'PFE48',
  'parcelforce-48-signed':       'PFE48SF',
  'parcelforce-am':              'PFEAM',
  'parcelforce-am-signed':       'PFEAMSF',
  'parcelforce-48-large':        'PFELG',
  'parcelforce-48-large-signed': 'PFELGSF',

  // ─── Parcelforce International ─────────────────────────────────────────────
  'parcelforce-ireland':         'PFIIX',
  'parcelforce-global-express':  'PFIGX',
  'parcelforce-priority-europe': 'PFIGPE',
  'parcelforce-priority-row':    'PFIGPG',

  // ─── Royal Mail International ──────────────────────────────────────────────
  'international-economy':              'IEOLP',
  'international-standard':             'ISOLP',
  'international-tracked':              'ITROLP',
  'international-tracked-heavier':      'ITHOLP',
  'international-tracked-heavier-comp': 'ITHCOLP',
  'international-tracked-signed':       'ITSOLP',
};

// Package format identifiers (Royal Mail terminology)
export const RM_PACKAGE_FORMATS = {
  'letter':        'letter',
  'large-letter':  'largeLetter',
  'small-parcel':  'smallParcel',
  'medium-parcel': 'mediumParcel',
  'parcel':        'parcel',
};

// ─── Auth helper ──────────────────────────────────────────────────────────────

function getAuthHeader() {
  const apiKey = process.env.RM_API_KEY;
  if (!apiKey) {
    throw new Error(
      'Royal Mail API key not set. Add RM_API_KEY to your .env file. ' +
      'Get yours from: Click & Drop > Settings > API credentials.'
    );
  }
  return `Bearer ${apiKey}`;
}

// ─── HTTP helper ──────────────────────────────────────────────────────────────

async function request(method, path, body = null, { binary = false } = {}) {
  const url = `${BASE_URL}${path}`;

  const headers = {
    'Authorization': getAuthHeader(),
    'Content-Type':  'application/json',
    'Accept':        binary ? 'application/pdf' : 'application/json',
  };

  const options = { method, headers };
  if (body) options.body = JSON.stringify(body);

  const response = await fetch(url, options);

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Royal Mail API ${response.status}: ${error}`);
  }

  if (binary) {
    const buffer = await response.arrayBuffer();
    return Buffer.from(buffer).toString('base64');
  }

  return response.json();
}

// ─── Create order ─────────────────────────────────────────────────────────────

/**
 * Create an order in Royal Mail Click & Drop
 *
 * @param {Object} params
 * @param {string} params.service              - Key from RM_SERVICES, or raw serviceCode
 * @param {string} params.packageFormat        - Key from RM_PACKAGE_FORMATS (default 'small-parcel')
 * @param {number} params.weightGrams          - Weight in grams
 * @param {Object} params.recipient            - { fullName, companyName?, addressLine1, addressLine2?, city, county?, postcode, countryCode?, phone?, email? }
 * @param {Object} params.sender               - { fullName?, companyName?, addressLine1, addressLine2?, city, county?, postcode, countryCode? }
 * @param {string} params.reference            - Your internal order reference
 * @param {number} params.subtotal             - Order subtotal in GBP
 * @param {number} params.shippingCost         - Shipping cost charged to customer in GBP
 * @param {number} params.total                - Order total in GBP
 * @param {string} params.despatchDate         - Planned despatch date YYYY-MM-DD (default: today)
 * @param {boolean} params.requireSignature    - Request signature on delivery
 * @param {string} params.safePlace            - Safe place instructions for unattended delivery
 * @param {string} params.notifyEmail          - Email for delivery notifications
 * @param {string} params.notifyPhone          - Phone/SMS for delivery notifications
 * @param {Object} params.dimensions           - { heightMm, widthMm, depthMm }
 * @param {string} params.goodsDescription     - Description of contents
 */
export async function createOrder(params) {
  const serviceCode = RM_SERVICES[params.service] || params.service || 'OLP1';
  const packageFormat = RM_PACKAGE_FORMATS[params.packageFormat] || params.packageFormat || 'smallParcel';

  const orderDate = new Date().toISOString();
  const despatchDate = params.despatchDate
    ? new Date(params.despatchDate).toISOString()
    : null;

  // Build recipient: fullName and companyName live inside the address object
  const recipientAddress = {
    addressLine1: params.recipient.addressLine1,
    city:         params.recipient.city,
    postTown:     params.recipient.city,
    countryCode:  params.recipient.countryCode || 'GB',
  };
  if (params.recipient.fullName)     recipientAddress.fullName     = params.recipient.fullName;
  if (params.recipient.companyName)  recipientAddress.companyName  = params.recipient.companyName;
  if (params.recipient.addressLine2) recipientAddress.addressLine2 = params.recipient.addressLine2;
  if (params.recipient.postcode)     recipientAddress.postcode     = params.recipient.postcode;
  if (params.recipient.county)       recipientAddress.county       = params.recipient.county;
  if (params.recipient.phone)        recipientAddress.phoneNumber  = params.recipient.phone;
  if (params.recipient.email)        recipientAddress.emailAddress = params.recipient.email;

  const recipient = { address: recipientAddress };

  // Billing address is required by the API unless AddressBookReference is used.
  // Default to the recipient address if the caller didn't supply a separate billing block.
  const billingSource = params.billing || params.recipient;
  const billingAddress = {
    addressLine1: billingSource.addressLine1,
    city:         billingSource.city,
    postTown:     billingSource.city,
    countryCode:  billingSource.countryCode || 'GB',
  };
  if (billingSource.fullName)     billingAddress.fullName     = billingSource.fullName;
  if (billingSource.companyName)  billingAddress.companyName  = billingSource.companyName;
  if (billingSource.addressLine2) billingAddress.addressLine2 = billingSource.addressLine2;
  if (billingSource.postcode)     billingAddress.postcode     = billingSource.postcode;
  if (billingSource.county)       billingAddress.county       = billingSource.county;
  if (billingSource.phone)        billingAddress.phoneNumber  = billingSource.phone;
  if (billingSource.email)        billingAddress.emailAddress = billingSource.email;

  const billing = { address: billingAddress };

  // Build sender address (optional: falls back to account address if omitted)
  let sender;
  if (params.sender) {
    const senderAddress = {
      addressLine1: params.sender.addressLine1,
      city:         params.sender.city,
      countryCode:  params.sender.countryCode || 'GB',
    };
    if (params.sender.fullName)     senderAddress.fullName     = params.sender.fullName;
    if (params.sender.companyName)  senderAddress.companyName  = params.sender.companyName;
    if (params.sender.addressLine2) senderAddress.addressLine2 = params.sender.addressLine2;
    if (params.sender.postcode)     senderAddress.postcode     = params.sender.postcode;
    if (params.sender.county)       senderAddress.county       = params.sender.county;

    sender = { address: senderAddress };
  }

  // Build package
  const pkg = {
    weightInGrams:           Math.round(params.weightGrams || 500),
    packageFormatIdentifier: packageFormat,
  };
  if (params.dimensions) {
    pkg.dimensions = {
      heightInMms: params.dimensions.heightMm,
      widthInMms:  params.dimensions.widthMm,
      depthInMms:  params.dimensions.depthMm,
    };
  }
  if (params.goodsDescription) {
    pkg.contents = [{
      name: params.goodsDescription,
      quantity: 1,
      unitValue: params.subtotal || 0,
      unitWeightInGrams: pkg.weightInGrams,
    }];
  }

  // Build postage details
  const postageDetails = { serviceCode };
  if (params.requireSignature) postageDetails.requestSignatureUponDelivery = true;
  if (params.safePlace)        postageDetails.safePlace = params.safePlace;

  // Notifications
  if (params.notifyEmail || params.notifyPhone) {
    postageDetails.sendNotificationsTo = {};
    if (params.notifyEmail) postageDetails.sendNotificationsTo.emailAddress = params.notifyEmail;
    if (params.notifyPhone) postageDetails.sendNotificationsTo.mobileNumber = params.notifyPhone;
  }

  // Build the order request
  const orderRequest = {
    recipient,
    orderDate,
    subtotal:           params.subtotal         ?? 0,
    shippingCostCharged: params.shippingCost    ?? 0,
    total:              params.total             ?? 0,
    packages:           [pkg],
    postageDetails,
  };
  if (despatchDate) orderRequest.plannedDespatchDate = despatchDate;

  if (params.reference) orderRequest.orderReference = params.reference;
  if (sender)           orderRequest.sender = sender;
  if (params.specialInstructions) orderRequest.specialInstructions = params.specialInstructions;

  orderRequest.billing = billing;

  const body = { items: [orderRequest] };
  const result = await request('POST', '/orders', body);

  // Response shape: { successCount, errorsCount, createdOrders: [...], failedOrders: [...] }
  if (result.errorsCount > 0 && result.successCount === 0) {
    const err = result.failedOrders?.[0]?.errors?.[0];
    throw new Error(`Royal Mail order failed: ${err?.errorMessage || JSON.stringify(result.failedOrders)}`);
  }

  const created = result.createdOrders?.[0];

  return {
    success:         true,
    orderIdentifier: created?.orderIdentifier,
    orderReference:  created?.orderReference || params.reference,
    status:          created?.status,
    service:         params.service,
    serviceCode,
    raw: created,
  };
}

// ─── Get label ────────────────────────────────────────────────────────────────

/**
 * Get the shipping label for an order (PDF binary, base64-encoded)
 *
 * @param {string} orderIdentifier - The orderIdentifier returned when creating the order
 * @returns {{ success, orderIdentifier, labelBase64, format }}
 */
export async function getLabel(orderIdentifier) {
  // Returns PDF binary. documentType + includeReturnsLabel are both required query params.
  const path = `/orders/${orderIdentifier}/label?documentType=postageLabel&includeReturnsLabel=false`;
  const labelBase64 = await request('GET', path, null, { binary: true });

  return {
    success: true,
    orderIdentifier,
    format: 'PDF',
    labelBase64,
  };
}

// ─── Get order ────────────────────────────────────────────────────────────────

/**
 * Get the current status and details of an order
 *
 * @param {string} orderIdentifier - The orderIdentifier returned when creating the order
 */
export async function getOrder(orderIdentifier) {
  const result = await request('GET', `/orders/${orderIdentifier}`);
  const order = Array.isArray(result) ? result[0] : result;

  return {
    success: true,
    orderIdentifier,
    status:         order?.status,
    trackingNumber: order?.trackingNumber,
    service:        order?.postageDetails?.serviceCode,
    despatchDate:   order?.plannedDespatchDate,
    raw: order,
  };
}

// ─── Cancel order ─────────────────────────────────────────────────────────────

/**
 * Cancel an order. Only possible before it has been manifested/despatched
 *
 * @param {string} orderIdentifier
 */
export async function cancelOrder(orderIdentifier) {
  // Click & Drop cancels pre-despatch orders via DELETE.
  const result = await request('DELETE', `/orders/${orderIdentifier}`);

  return {
    success: true,
    orderIdentifier,
    message: 'Cancellation request sent.',
    raw: result,
  };
}
