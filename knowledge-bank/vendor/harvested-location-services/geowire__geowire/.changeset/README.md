# Changesets

이 디렉터리는 [Changesets](https://github.com/changesets/changesets)로 버전과 CHANGELOG를 관리한다.

변경을 낼 때:

```bash
pnpm changeset
```

로 어떤 패키지가 major/minor/patch인지와 요약을 기록한다. `main`에 머지되면
Release 워크플로가 "Version Packages" PR을 만들고, 그 PR이 머지되면 npm에 publish 한다.
