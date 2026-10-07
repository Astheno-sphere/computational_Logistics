using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace TargetGrps.Partelisto.Mcp.Infrastructure;

public static class InfrastructureServiceExtensions
{
    public static IServiceCollection AddPartelistoGateway(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddOptions<GatewayOptions>()
            .Bind(configuration.GetSection(GatewayOptions.SectionName))
            .Validate(o => !string.IsNullOrWhiteSpace(o.BaseUrl), "Gateway:BaseUrl is required.")
            .ValidateOnStart();

        services.AddHttpClient<IPartelistoGatewayClient, PartelistoGatewayClient>((sp, client) =>
            {
                GatewayOptions opts = sp.GetRequiredService<IOptions<GatewayOptions>>().Value;
                client.BaseAddress = new Uri(opts.BaseUrl);
            })
            .AddStandardResilienceHandler();

        return services;
    }
}
