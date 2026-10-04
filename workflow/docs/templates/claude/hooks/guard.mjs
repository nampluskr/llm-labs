#!/usr/bin/env node
// PreToolUse guard
//
// 막는 사고
//   1. docs/history/ 아래 기존 파일이 사후에 수정·삭제되어 마감 기록이 바뀌는 것
//   2. backlog.json 이 CLI 를 거치지 않고 편집되어 SSOT 가 무너지는 것
//
// 설치 후 반드시 차단 증명을 돌린다 (docs/HARNESS.md 5절).
// 등록된 것과 동작하는 것은 다르다.

import { existsSync } from 'node:fs';
import { resolve, sep } from 'node:path';

const WRITE_TOOLS = new Set(['Write', 'Edit', 'NotebookEdit']);

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  let ev;
  try {
    ev = JSON.parse(raw);
  } catch {
    process.exit(0); // 입력을 못 읽으면 통과시킨다. 막는 것은 확실할 때만
  }

  const tool = ev.tool_name;
  const input = ev.tool_input ?? {};

  if (WRITE_TOOLS.has(tool)) {
    checkPath(input.file_path);
  } else if (tool === 'Bash') {
    checkCommand(input.command);
  }

  process.exit(0);
});

function norm(p) {
  return resolve(p).split(sep).join('/');
}

function checkPath(filePath) {
  if (!filePath) return;
  const p = norm(filePath);

  // 새로 만드는 것은 허용한다. 마감 시 스냅샷 생성이 여기 해당한다.
  if (p.includes('/docs/history/') && existsSync(filePath)) {
    block(
      'docs/history/ 아래 기존 파일은 수정·삭제할 수 없다.\n' +
      '마감 기록은 불변이다. 고쳐야 할 것이 있으면 다음 minor 로 넘긴다.'
    );
  }

  if (p.endsWith('/backlog.json')) {
    block(
      'backlog.json 은 직접 편집하지 않는다. backlog CLI 로 변경한다.\n' +
      '계획 밖의 작업이라면 docs/current/PROGRESS.md 에 적는다.'
    );
  }
}

function checkCommand(cmd) {
  if (!cmd) return;
  const c = cmd.replace(/\\/g, '/');

  const touchesHistory = /docs\/history\//.test(c);
  const destructive = /\b(rm|mv|del|move|Remove-Item|Move-Item)\b/.test(c) || />\s*[^|]*docs\/history\//.test(c);
  if (touchesHistory && destructive) {
    block('docs/history/ 아래를 삭제·이동·덮어쓸 수 없다. 마감 기록은 불변이다.');
  }

  if (/>\s*[^|]*backlog\.json/.test(c) || /\bbacklog\.json\b/.test(c) && destructive) {
    block('backlog.json 은 CLI 로만 변경한다.');
  }
}

function block(msg) {
  process.stderr.write(msg + '\n');
  process.exit(2); // 2 = 도구 호출 차단, stderr 가 에이전트에게 전달된다
}
