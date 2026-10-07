namespace TargetGrps.Partelisto.Mcp.Application;

/// <summary>
/// The exact GraphQL documents each tool sends to the api-gateway. Kept as one reviewable place so a
/// change here is an explicit, auditable diff — in particular, so nobody can widen a field selection to
/// include guest PII (email, phone, document numbers) without it showing up in review. Every operation
/// here already exists in the backoffice/booking/guestdocs schemas and is gated by the OwnerAccess
/// policy server-side; this file only selects which of the already-exposed fields the MCP tools use.
/// </summary>
public static class GatewayQueries
{
    public const string ListProperties = """
        query McpListProperties($includeArchived: Boolean) {
          properties(includeArchived: $includeArchived) {
            id
            name
            address
            municipality
            province
            isArchived
          }
        }
        """;

    public const string ListBookings = """
        query McpListBookings($skip: Int, $take: Int) {
          bookingsPage(skip: $skip, take: $take) {
            totalCount
            items {
              id
              propertyId
              checkIn
              checkOut
              status
              shareLink { expiresAt }
              guestContact { name }
            }
          }
        }
        """;

    public const string GetGuestFormStatus = """
        query McpGuestFormStatus($bookingId: String!) {
          submissionStatus(bookingId: $bookingId) {
            status
          }
        }
        """;

    public const string ListSesStatuses = """
        query McpListSesStatuses($bookingIds: [String!]!) {
          sesSubmissionStatuses(bookingIds: $bookingIds) {
            bookingId
            status
            attempts
            lastError
            sesReference
            loteId
            lastAttemptAt
          }
        }
        """;

    public const string GetUsageSummary = """
        query McpUsageSummary {
          partelistoUsageInfo {
            tier
            trialActive
            trialDaysRemaining
            propertiesCreatedThisMonth
            templatesCreatedThisMonth
            bookingsCreatedThisMonth
            limits {
              maxProperties
              maxTemplates
              maxBookingsPerMonth
            }
          }
        }
        """;

    public const string SendGuestLink = """
        mutation McpSendGuestLink($input: SendGuestLinkInput!) {
          sendGuestLink(input: $input) {
            sent
            recipient
            error
            expiresAt
          }
        }
        """;

    // Used only to auto-pick a template when create_booking is called without one — id and archived
    // state are all that's needed to decide "exactly one active template" vs. "ask the caller".
    public const string ListTemplatesForProperty = """
        query McpListTemplates($propertyId: String!, $includeArchived: Boolean) {
          templates(propertyId: $propertyId, includeArchived: $includeArchived) {
            id
            archivedAt
          }
        }
        """;

    public const string CreateBooking = """
        mutation McpCreateBooking($input: CreateBookingInput!) {
          createBooking(input: $input) {
            booking {
              id
              propertyId
              templateId
              checkIn
              checkOut
              status
            }
          }
        }
        """;
}
