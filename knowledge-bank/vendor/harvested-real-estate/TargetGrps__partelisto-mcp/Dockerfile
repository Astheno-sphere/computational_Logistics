FROM mcr.microsoft.com/dotnet/sdk:10.0-alpine AS restore
WORKDIR /app
COPY . .
# Unlike the other TargetGrps services, this one has no TargetGrps.BuildingBlocks.* dependency (it owns
# no data — no Mongo, no tenancy middleware), so restore needs no private GitHub package source/token.
# If a BuildingBlocks package is ever added, mirror the GH_ACCOUNT_TARGETGRPS/GH_TOKEN_TARGETGRPS
# `dotnet nuget update source github` step from the sibling services' Dockerfiles here.
RUN find ./ -type f -name "*.csproj" -exec dotnet restore {} \;

FROM restore AS build
ARG BUILDCONFIG=Release
ARG FILE_VERSION="1.0.0.0"
ARG INFORMATIONAL_VERSION="1.0"
ARG APP_VERSION="1.0.0"
ARG CI_BUILD=true
COPY . .
RUN dotnet build -c "$BUILDCONFIG" --no-restore /p:PackageVersion="$APP_VERSION" /p:Version="$APP_VERSION" /p:FileVersion="$FILE_VERSION" /p:InformationVersion="$INFORMATIONAL_VERSION"

FROM build AS publish
ARG BUILDCONFIG=Release
# -o must NOT be /app: that's also WORKDIR, which already holds the source tree (src/...) from the
# COPY above. Publishing --no-build into the same directory that already contains the built project's
# own source/obj tree silently skips copying Content items (appsettings.json, appsettings.*.json) -
# a known MSBuild incremental-cache quirk when build and publish share one obj/ directory. Confirmed
# by direct repro: publishing to a fresh directory copies appsettings.json; publishing to /app does not,
# and the resulting image throws "Keycloak:Authority is not configured" at startup with no appsettings
# files present at all. Publishing to a distinct directory sidesteps it entirely.
RUN dotnet publish src/TargetGrps.Partelisto.Mcp.Api/TargetGrps.Partelisto.Mcp.Api.csproj -c "$BUILDCONFIG" -o /out --no-build

FROM mcr.microsoft.com/dotnet/aspnet:10.0-alpine AS runtime
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=0
RUN apk add --no-cache icu-libs
WORKDIR /app
COPY --from=publish /out .
# uid/gid 1000 pinned explicitly: the k8s deployment sets runAsUser/runAsGroup: 1000 (matching the
# other TargetGrps services' securityContext), so this has to be the same 1000, not whatever Alpine's
# adduser would pick by default.
RUN adduser -D -u 1000 buildadmin && chown buildadmin:buildadmin /app /app/*
USER buildadmin
EXPOSE 8080
ARG COMMIT_SHA
ENV SENTRY_RELEASE=${COMMIT_SHA} REVISION=${COMMIT_SHA}
ENV ASPNETCORE_URLS=http://*:8080
ENTRYPOINT ["dotnet", "TargetGrps.Partelisto.Mcp.Api.dll"]

FROM build AS tests
ARG BUILDCONFIG=Release
ENV TESTBUILDCONFIG=$BUILDCONFIG
RUN dotnet tool restore
ENTRYPOINT dotnet test --collect:"XPlat Code Coverage" -c "$TESTBUILDCONFIG" --no-build --verbosity normal --settings coverlet.runsettings\
  --logger:"junit;LogFileName=TestResults.{assembly}.{framework}.xml;verbosity=normal"\
  --logger:"console;verbosity=normal"
