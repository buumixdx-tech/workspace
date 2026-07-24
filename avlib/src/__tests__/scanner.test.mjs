// Unit tests for scanner.extractCodeAndPart / parsePartLabel / parsePartIndex
// Run: node src/__tests__/scanner.test.mjs
import { extractCodeAndPart, parsePartLabel, parsePartIndex } from '../scanner.js';

let pass = 0, fail = 0;
const tests = [
  // ===== FC2 短番号(本次 bug 修复的核心) =====
  { in: 'FC2-506923.mp4',         code: 'fc2-506923',     part: null },
  { in: 'fc2-506923.mp4',         code: 'fc2-506923',     part: null },
  { in: 'FC2_506923.mp4',         code: 'fc2-506923',     part: null },
  { in: 'FC2 506923.mp4',         code: 'fc2-506923',     part: null },
  { in: 'fc2-506923-A.mp4',       code: 'fc2-506923',     part: 'A' },
  { in: 'fc2-506923-cd1.mp4',     code: 'fc2-506923',     part: 'cd1' },     // parsePart 不改大小写
  { in: 'fc2-506923-1.mp4',       code: 'fc2-506923',     part: '1' },
  { in: 'FC2-1234567.mp4',        code: 'fc2-1234567',    part: null },     // 7 位数

  // ===== FC2 PPV 长格式(老规则不能被新规则覆盖) =====
  { in: 'fc2-ppv-506923.mp4',     code: 'fc2-ppv-506923', part: null },
  { in: 'FC2-PPV-506923.mp4',     code: 'fc2-ppv-506923', part: null },
  { in: 'FC2PPV-506923.mp4',      code: 'fc2-ppv-506923', part: null },
  { in: 'fc2-ppv-506923-A.mp4',   code: 'fc2-ppv-506923', part: 'A' },

  // ===== 字母+数字混排 prefix =====
  { in: 'T28-123.mp4',            code: 't28-123',        part: null },
  { in: 'H4610-001.mp4',          code: 'h4610-001',      part: null },
  { in: 'A2C-12.mp4',             code: 'a2c-12',         part: null },

  // ===== 纯字母 prefix 不能被 fallback 误吃(回归) =====
  { in: 'juq-426.mp4',            code: 'juq-426',        part: null },
  { in: 'vdd-157.mp4',            code: 'vdd-157',        part: null },
  { in: 'mvg-012.mp4',            code: 'mvg-012',        part: null },
  { in: 'isrd-001.mp4',           code: 'isrd-001',       part: null },

  // ===== 纯字母 prefix(老规则不能回归) =====
  { in: 'ABP-123.mp4',            code: 'abp-123',        part: null },
  { in: 'SSIS-001.mp4',           code: 'ssis-001',       part: null },
  { in: 'achj-040.mp4',           code: 'achj-040',       part: null },
  { in: 'dpmb-001.mp4',           code: 'dpmb-001',       part: null },
  { in: 'rvg-132.mp4',            code: 'rvg-132',        part: null },
  { in: 'tt-013.mp4',             code: 'tt-013',         part: null },
  { in: 'DPMB-001.mp4',           code: 'dpmb-001',       part: null },
  { in: 'AB-1234567.mp4',         code: 'ab-1234567',     part: null },     // 7 位 suffix

  // ===== 不该被识别的(返回 null) =====
  { in: '506923.mp4',             code: null,             part: null },     // 纯数字 prefix
  { in: '123-456.mp4',            code: null,             part: null },     // 纯数字 prefix
  { in: 'random-video.mp4',       code: null,             part: null },     // 没数字
  { in: 'FC2 [1080p].mp4',        code: null,             part: null },     // FC2 后接非数字

  // ===== parsePartIndex 派生测试(用合法 code+part 文件名) =====
  // 注意:这里 code 至少 3 位数字,才能让 -N 被识别为 part 而不是 suffix
  { in: 'mvg-012-1.mp4',          idx: 1 },
  { in: 'mvg-012-2.mp4',          idx: 2 },
  { in: 'mvg-012-3.mp4',          idx: 3 },
  { in: 'mvg-012-4.mp4',          idx: 4 },
  { in: 'mvg-012-12.mp4',         idx: 12 },
  { in: 'mvg-012-上.mp4',         idx: 1 },
  { in: 'mvg-012-下.mp4',         idx: 2 },
  { in: 'mvg-012-A.mp4',          idx: 1 },
  { in: 'mvg-012-B.mp4',          idx: 2 },
  { in: 'mvg-012-C.mp4',          idx: 3 },
  { in: 'mvg-012-CD1.mp4',        idx: 1 },
  { in: 'mvg-012-CD12.mp4',       idx: 12 },
  { in: 'mvg-012.mp4',            idx: 1 },  // 无 part → 默认 1
];

for (const t of tests) {
  const r = extractCodeAndPart(t.in);
  const idx = parsePartIndex(t.in);
  let ok = true;
  let why = [];
  if (t.code !== undefined) {
    const got = r?.code ?? null;
    if (got !== t.code) { ok = false; why.push(`code: got ${JSON.stringify(got)}, want ${JSON.stringify(t.code)}`); }
  }
  if (t.part !== undefined) {
    const got = r?.part ?? null;
    if (got !== t.part) { ok = false; why.push(`part: got ${JSON.stringify(got)}, want ${JSON.stringify(t.part)}`); }
  }
  if (t.idx !== undefined) {
    if (idx !== t.idx) { ok = false; why.push(`idx: got ${idx}, want ${t.idx}`); }
  }
  if (ok) {
    pass++;
    console.log('  ✓', t.in);
  } else {
    fail++;
    console.log('  ✗', t.in, '→', why.join('; '));
  }
}

console.log(`\n${pass} pass, ${fail} fail`);
process.exit(fail > 0 ? 1 : 0);
