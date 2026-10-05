#!/usr/bin/env node
// Stop hook
//
// 막는 사고
//   코드는 고쳤는데 PROGRESS.md 에 아무것도 안 남아, 진행이 커밋에만 있고
//   사람이 열어서 확인할 수 없게 되는 것.
//
// 판정 (llm-labs): 연습 폴더(NN-category/NN-name/)마다 따로 본다. 이번 세션에서 그 연습의
// docs/ 밖 파일이 바뀌었는데 그 연습의 docs/current/PROGRESS.md 는 그대로면 막는다.
// 저장소 루트·docs/ 의 파일(INTENT·ROADMAP·DECISIONS·refs·labs·workflow/·.claude/ 등)은 판정하지 않는다.
//
// 프로젝트 성격에 따라 시끄러울 수 있다. 그때는 매처를 좁히거나 이 hook 을 뺀다.
// 빼기로 했다면 왜 뺐는지 저장소 docs/DECISIONS.md 에 남긴다.

import { execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

const LAB = /^(\d{2}-[^/]+\/\d{2}-[^/]+)\/(.*)$/;

let changed;
try {
  // -uall: 새로 만든 폴더가 폴더 이름 하나로 뭉쳐 보이지 않게 파일 단위로 받는다
  changed = execSync('git status --porcelain -uall', { encoding: 'utf8' })
    .split('\n')
    .map((l) => l.slice(3).trim().replace(/^"|"$/g, ''))
    .filter(Boolean);
} catch {
  process.exit(0); // git 이 없으면 판정하지 않는다
}

const labs = new Map(); // lab → { work, progress }
for (const f of changed) {
  const m = LAB.exec(f);
  if (!m) continue;
  const [, lab, rest] = m;
  const s = labs.get(lab) ?? { work: false, progress: false };
  if (rest === 'docs/current/PROGRESS.md') s.progress = true;
  else if (!rest.startsWith('docs/')) s.work = true;
  labs.set(lab, s);
}

// INIT 전(docs/current/ 없음)의 연습 폴더는 기획 문서만 있는 단계라 판정하지 않는다.
// PROGRESS.md 는 INIT 이 docs/current/ 와 함께 만든다.
const root = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
const missing = [...labs]
  .filter(([lab, s]) => s.work && !s.progress && existsSync(join(root, lab, 'docs', 'current')))
  .map(([lab]) => lab);

if (missing.length > 0) {
  process.stderr.write(
    missing.map((lab) => `${lab}: 작업 파일이 바뀌었는데 ${lab}/docs/current/PROGRESS.md 에 기록이 없다.`).join('\n') +
    '\n무엇을 했고, 결과가 무엇이고, 어떻게 검증했는지 남긴 뒤 마친다.\n' +
    '계획 밖의 작업이면 "계획 외 개선" 구간에 적는다.\n'
  );
  process.exit(2);
}

process.exit(0);
