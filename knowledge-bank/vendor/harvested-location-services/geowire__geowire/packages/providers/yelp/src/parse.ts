import { CountryCode } from "@geowirehq/schema";
import type { Address, Business, Contact, Review } from "@geowirehq/schema";
import type { ProviderPlace } from "@geowirehq/provider-sdk";

/** Yelp Fusion business (관심 필드만) */
export interface YelpBusiness {
  id?: string;
  name?: string;
  coordinates?: { latitude?: number; longitude?: number };
  location?: {
    address1?: string;
    city?: string;
    state?: string;
    zip_code?: string;
    country?: string; // ISO alpha-2
    display_address?: string[];
  };
  categories?: Array<{ alias?: string; title?: string }>;
  phone?: string;
  display_phone?: string;
  rating?: number; // 0~5 (Yelp는 이미 5점 척도)
  review_count?: number;
  price?: string; // "$".."$$$$"
  url?: string; // Yelp 페이지 URL
  image_url?: string;
  photos?: string[]; // details 응답에만
}

/** Yelp review (details 후속 /reviews 응답) */
export interface YelpReview {
  text?: string;
  rating?: number;
  user?: { name?: string };
  time_created?: string;
}

/** "$".."$$$$" → 1..4 */
function parsePrice(price: string | undefined): number | undefined {
  if (!price) return undefined;
  const n = price.length;
  return n >= 1 && n <= 4 ? n : undefined;
}

/** Yelp business → ProviderPlace. 좌표·id·이름 없으면 null */
export function parseYelpBusiness(raw: YelpBusiness, reviews?: YelpReview[]): ProviderPlace | null {
  const latitude = raw.coordinates?.latitude;
  const longitude = raw.coordinates?.longitude;
  if (typeof latitude !== "number" || typeof longitude !== "number") return null;
  if (!raw.id) return null;
  const name = raw.name?.trim();
  if (!name) return null;

  const place: ProviderPlace = {
    providerPlaceId: raw.id,
    name,
    categories: (raw.categories ?? [])
      .map((c) => c.title?.trim())
      .filter((t): t is string => !!t),
    location: { latitude, longitude },
  };

  const loc = raw.location;
  if (loc) {
    const address: Address = {};
    if (loc.display_address?.length) address.formatted = loc.display_address.join(", ");
    if (loc.address1) address.street = loc.address1;
    if (loc.city) address.city = loc.city;
    if (loc.state) address.region = loc.state;
    if (loc.zip_code) address.postalCode = loc.zip_code;
    if (loc.country) {
      const cc = CountryCode.safeParse(loc.country.toUpperCase());
      if (cc.success) address.country = cc.data;
    }
    if (Object.keys(address).length > 0) place.address = address;
  }

  const contact: Contact = {};
  const phone = raw.phone || raw.display_phone;
  if (phone) contact.phone = phone;
  if (raw.url) contact.website = raw.url; // Yelp 리스팅 URL(정본 링크)
  if (Object.keys(contact).length > 0) place.contact = contact;

  // 역할 소싱(US 비즈니스): 평점(이미 0~5)·리뷰 수·가격대·사진.
  const business: Business = {};
  if (typeof raw.rating === "number") business.rating = Math.max(0, Math.min(5, raw.rating));
  if (typeof raw.review_count === "number") business.reviewCount = raw.review_count;
  const price = parsePrice(raw.price);
  if (price != null) business.priceLevel = price;
  const photos = (raw.photos ?? []).filter((u): u is string => typeof u === "string");
  if (photos.length > 0) business.photos = photos;
  else if (raw.image_url) business.photos = [raw.image_url];
  if (reviews?.length) {
    const parsed = reviews.map(parseYelpReview).filter((r): r is Review => r !== null);
    if (parsed.length > 0) business.reviews = parsed;
  }
  if (Object.keys(business).length > 0) place.business = business;

  return place;
}

function parseYelpReview(raw: YelpReview): Review | null {
  const text = raw.text?.trim();
  const rating = typeof raw.rating === "number" ? Math.max(0, Math.min(5, raw.rating)) : undefined;
  if (!text && rating === undefined) return null;
  const review: Review = { source: "yelp" };
  if (text) review.text = text;
  if (rating !== undefined) review.rating = rating;
  const author = raw.user?.name?.trim();
  if (author) review.author = author;
  if (raw.time_created) {
    // Yelp time_created는 "2016-08-29 00:41:13" (UTC) → ISO
    const iso = raw.time_created.replace(" ", "T") + "Z";
    if (!Number.isNaN(Date.parse(iso))) review.time = iso;
  }
  return review;
}

export function parseYelpBusinesses(businesses: readonly YelpBusiness[] | undefined): ProviderPlace[] {
  const out: ProviderPlace[] = [];
  for (const raw of businesses ?? []) {
    const p = parseYelpBusiness(raw);
    if (p) out.push(p);
  }
  return out;
}
