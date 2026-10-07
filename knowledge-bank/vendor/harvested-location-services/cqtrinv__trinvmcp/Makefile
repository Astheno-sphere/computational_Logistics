work : increment.version dist/index.js

create.container : upgrade.package.json
	docker buildx build -t trinv/mcp .

create.local : upgrade.package.json dist/index.js

MAC_CONFIG_DIR=~/Library/'Application Support'/Claude

test.local.js : dist/index.js cdc-node-js.json
	[ -d ${MAC_CONFIG_DIR} ] && \
	  cp -p cdc-mac-node-js.json \
		${MAC_CONFIG_DIR}/claude_desktop_config.json
	cp -p cdc-node-js.json ~/.config/Claude/claude_desktop_config.json
	tail -f ~/.config/Claude/logs/mcp.log &
	{ which claude-desktop && claude-desktop ; } || \
		open -a claude

test.local.ts : src/index.ts cdc-node-ts.json
	-[ -d ${MAC_CONFIG_DIR} ] && \
	  cp -p cdc-mac-node-ts.json \
		${MAC_CONFIG_DIR}/claude_desktop_config.json
	cp -p cdc-node-ts.json ~/.config/Claude/claude_desktop_config.json
	tail -f ~/.config/Claude/logs/mcp.log &
	{ which claude-desktop && claude-desktop ; } || \
		open -a claude

upgrade.package.json : 
	jq . < package.json > /dev/null
	npm outdated || npm update

dist/index.js : upgrade.package.json src/index.ts 
	-rm -rf dist
	tsc
	chmod +x dist/index.js

save.claude.config :
	tar czf claude-config.tgz -C ../../.config/ Claude
	tar tzf claude-config.tgz

copy2bibou :
	rsync -avu . bibou:TRINV/MCP/

publish : increment.version dist/index.js
	jq . < package.json
	npm publish --access public

publish.mcpb : manifest.json
#	npx mcpb init
	npx mcpb validate manifest.json
	npx mcpb pack . mcp-trinv-server.mcpb

increment.version :
	npm version patch --no-git-tag-version
	./propagateVersion.js 

run.gemini :
	npx gemini
