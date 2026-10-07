#!/usr/bin/env node

import { McpServer, ResourceTemplate }
 from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport }
 from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import z from "zod";
import minimist from 'minimist';
//import { HttpServerTransport } from "./http.js";

const VERSION = "0.0.7";

// Initialize the server
const server = new McpServer({
    name: "mcptrinv",
    version: VERSION
});

type County = {
    name: string,
    inseeid: string,
    postalid: string,
    departmentid: string,
    latitude: number,
    longitude: number
};
type CountyByFragmentResponse = {
    fragment: string,
    counties: County[]
};
type Area = {
    name: string,
    area: number,
    latitude: number,
    longitude: number,
    address?: string
};
type AreasByCountyAndSurfaceResponse = {
    areascount: number,
    inseeid: string,
    areamin: number,
    areamax: number,
    status?: string,
    areas: Area[]
};

const fragment2countiesCache = new Map<string, County[]>();
const county2inseeidCache = new Map<string, string>();

// Add a tool: search counties with a fragment of their name
server.registerTool(
    "trinv-chercher-commune", {
        description: `
Cet outil permet de chercher des communes en France à partir
d'un fragment de leur nom (c'est-à-dire une série de lettres consécutives).
Ainsi, chercher BEURD conduit à trouver la commune de TREBEURDEN.
Il faut cependant être spécifique car chercher, par exemple, SAINT
mène à 4834 communes: un si grand nombre de résultats ne peut être listé
ni utilement, ni agréablement.

Les communes trouvées sont accompagnées de leur code INSEE, de leurs
coordonnées (latitude, longitude). Certaines communes ont changé de
nom ou ont été regroupées avec d'autres.

Exemples de questions:
- Quelle est la commune nommée BEURD ?
- Dis-moi quelles sont les communes ayant DOUS dans leur nom ?

[Pour en savoir plus](https://doc.trinv.fr/trinv-mcp-server)
`,
        inputSchema: { fragment: z.string() },
    },
    async function ({ fragment }: { fragment: string }) {
        //return await search_county(fragment);
        fragment = fragment.toUpperCase();
        const url = `https://trinv.fr/api/countybyfragment.json`;
        const response = await fetch(url, {
            method: 'POST',
            mode: 'cors',
            redirect: 'follow',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ fragment })
        });
        if ( response.ok ) {
            const json : CountyByFragmentResponse = await response.json();
            let text : string = '';
            fragment2countiesCache.set(fragment, json.counties);
            json.counties.forEach(c => {
                county2inseeidCache.set(c.name, c.inseeid);
            });
            if ( json.counties.length === 0 ) {
		text = `# SEARCH RESULT 
Aucune commune ne porte un nom comportant ce fragment \`${json.fragment}\`

# STRUCTURED DATA
\`\`\`json
${JSON.stringify(json, null, 2)}
\`\`\`
`;
	    } else if ( json.counties.length === 1 ) {
                const county : County = json.counties[0] as County;
                // take care of .obsolete, .seealso, etc.
                text = `# SEARCH RESULT 
Voici la commune concernée: ${county.name}
ainsi que son code INSEE: ${county.inseeid}.

# STRUCTURED DATA
\`\`\`json
${JSON.stringify(json, null, 2)}
\`\`\`
`;
            } else {
                text = `# SEARCH RESULT 
Voici les ${json.counties.length} communes de France ayant
ce fragment de nom \`${json.fragment}\`:
${json.counties.map(formatCounty).join('\n')}

# STRUCTURED DATA
\`\`\`json
${JSON.stringify(json, null, 2)}
\`\`\`
`;
            }
            return {
                content: [{ type: "text", text }]
            };
        } else {
            console.error(response);
            throw new Error('probleme');
        }
    }
);

//   Allow Claude to use "trinv-chercher-commune"
// Questions:
// Cherche des communes avec RIAQ dans leur nom
//    => locmariaquer
// Y a-t-il des communes nommées DOUS
//    => 8 communes BEDOUS, BUROSSE-MENDOUSSE, ...

// Add a tool: search areas within county
server.registerTool(
    "trinv-chercher-parcelle", {
        description: `
Cet outil permet de rechercher des parcelles cadastrales ayant une
certaine surface au sein d'une commune de France. Cette recherche s'effectue,
le plus souvent, en deux phases:
1. Spécifier la commune qui vous intéresse
2. Indiquer la taille (en m²) de la parcelle recherchée.

Bien identifier la commune implique de connaître son code INSEE.

Exemples de questions:
- Y a t-il une parcelle de surface 247 m² dans BEDOUS
- Je cherche une parcelle dans BEURD faisant 333 m²

[Pour en savoir plus](https://doc.trinv.fr/trinv-mcp-server)
`,
        inputSchema: { fragment: z.string(), area: z.number() },
    },
    async function ({ fragment, area }: { fragment: string, area: number }) {
        fragment = fragment.toUpperCase();
        let inseeid : string | undefined =
            county2inseeidCache.get(fragment);
        const counties : County[] | undefined =
	      fragment2countiesCache.get(fragment);

        if ( ! inseeid ) {
            if ( ! counties ) {
                throw new Error(`Peut-être faut-il que vous m'indiquiez
plus précisément la commune que vous cherchez.`);
            } else if ( counties.length === 1 ) {
		const county = counties[0] as County;
                fragment = county.name;
                inseeid = county.inseeid;
            } else {
                throw new Error(`Trop de communes ont ces lettres
dans leur nom!`);
            }
        }

        const url = `https://trinv.fr/api/areas.json?` +
              `inseeid=${inseeid}&` +
              `surfacemin=${area}`;
        const response = await fetch(url, {
            method: 'GET',
            mode: 'cors',
            redirect: 'follow',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        });
        if ( response.ok ) {
            const json : AreasByCountyAndSurfaceResponse =
		  await response.json();
            let text : string = '';
            if ( json.areas.length === 0 ) {
                text = `# SEARCH RESULT
Aucune parcelle cadastrale ne correspond à une telle surface.

# STRUCTURED DATA
\`\`\`json
${JSON.stringify(json, null, 2)}
\`\`\`
`;
            } else if ( json.areas.length === 1 ) {
                const area = json.areas[0] as Area;
                const geourl = `https://trinv.fr/parcelle?cadastreid=${area.name}`;
                text = `# SEARCH RESULT
Voici la référence de la parcelle cadastrale concernée: ${area.name}.
${area.address ? `Son adresse est ${area.address}.` : ''}
Elle est située en [${area.latitude} ${area.longitude}](${geourl})

# STRUCTURED DATA
\`\`\`json
${JSON.stringify(json, null, 2)}
\`\`\`
`;
            } else {
                text = `# SEARCH RESULT
Voici les parcelles cadastrales ayant cette surface:
${json.areas.map(formatArea).join('\n')}

# STRUCTURED DATA
\`\`\`json
${JSON.stringify(json, null, 2)}
\`\`\`
`;
            }
            return {
                content: [{ type: "text", text }]
            };
        } else {
            console.error(response);
            throw new Error('probleme');
        }
    }
);

function formatCounty (c: County) : string {
    return `- ${c.name} (code INSEE: ${c.inseeid})`;
}

function formatArea (area: Area): string {
    return area.name;
}

//   Allow Claude to use "trinv-chercher-parcelle"
// Questions:
// Y a t-il une parcelle de surface 247 m² dans BEDOUS
//    64104-000-A-626 Place de l'École, 64490 Bedous     # Screenshots/1.png
// Je cherche une parcelle dans BEURD faisant 333 m²
//    plusieurs dans TREBEURDEN                          # Screenshots/2.png
// Je cherche une parcelle dans DOUS faisant 333 m²
//    plusieurs communes avec DOUS                       # Screenshots/3.png
// Je cherche une parcelle dans XIT                      # Screenshots/4.png

// Tool trinv-localiser-parcelle




/*
  Prompts are help, triggered by the user, to help formulating a
  question to the assistant. 


server.prompt(
    "trinv-chercher-commune",
    { fragment: z.string() },
    function ({ fragment }) {
        return {
            messages: [{
                role: "user",
                content: {
                    type: "text",
                    text: `Je cherche des communes en France
dont le nom comporte, dans l'ordre, les lettres suivantes:
\`${fragment}\` `
                }
            }]
        };
    }
);

server.prompt(
    "trinv-chercher-parcelle",
    { countyname: z.string(), area: z.number() },
    function ({ countyname, area }) {
        return {
            messages: [
                {
                    role: "user",
                    content: {
                        type: "text",
                        text: `Je cherche des parcelles cadastrales
ayant une surface de ${area} m² au sein de la commune \`${countyname}\`.`
                    }
                }
            ]
        };
    }
);

*/

///////////// FUTURE add --transport= option

// Run the server
async function runServer() {
  const argv = minimist(process.argv.slice(2));

  if (argv.http) {
    //const port = argv.port || 3000;
    //const transport = new HttpServerTransport(port);
    //await server.connect(transport);
  } else if (argv.stdio || !argv.http) {
    const transport = new StdioServerTransport();
    await server.connect(transport);
  }
}

runServer().catch((error) => {
    console.error("server error", error);
});
