const test = require('node:test');
const assert = require('node:assert/strict');
const {
  parseSkillSourceInput,
  formatSkillSourceRepo,
} = require('../out/skillMarketplace/parseSkillSourceInput');

test('parseSkillSourceInput accepts common GitHub and GitLab forms', () => {
  const github = parseSkillSourceInput('https://github.com/anthropics/skills/tree/main/skills');
  assert.equal(github.ok, true);
  assert.equal(github.source.owner, 'anthropics');
  assert.equal(github.source.repo, 'skills');
  assert.equal(github.source.skillsPath, 'skills');

  const short = parseSkillSourceInput('anthropics/skills', 'skills');
  assert.equal(short.ok, true);
  assert.equal(formatSkillSourceRepo(short.source), 'github.com/anthropics/skills');

  const gitlab = parseSkillSourceInput('https://gitlab.com/group/sub/project/-/tree/main/lib/skills');
  assert.equal(gitlab.ok, true);
  assert.equal(gitlab.source.owner, 'group/sub');
  assert.equal(gitlab.source.repo, 'project');
  assert.equal(gitlab.source.skillsPath, 'lib/skills');

  const selfHosted = parseSkillSourceInput('git@git.fiblab.net:llmsim/agentsociety.git');
  assert.equal(selfHosted.ok, true);
  assert.equal(selfHosted.source.platform, 'gitlab');
  assert.equal(selfHosted.source.baseUrl, 'https://git.fiblab.net');
});

test('parseSkillSourceInput rejects empty, http, and invalid input', () => {
  assert.deepEqual(parseSkillSourceInput(''), { ok: false, error: 'empty' });
  assert.deepEqual(parseSkillSourceInput('not a repo'), { ok: false, error: 'invalid' });
  assert.deepEqual(parseSkillSourceInput('http://github.com/owner/repo'), { ok: false, error: 'invalid' });
  assert.deepEqual(parseSkillSourceInput('https://127.0.0.1/owner/repo'), { ok: false, error: 'invalid' });
});
