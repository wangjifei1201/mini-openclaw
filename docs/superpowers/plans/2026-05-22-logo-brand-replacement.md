# Logo Brand Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the top navbar `BaseClaw` text brand with the provided DeepClaw logo and update the welcome text to `欢迎使用 DeepClaw`.

**Architecture:** Use Next.js public static assets for the logo. Keep the change limited to the navbar brand rendering and welcome empty-state copy, without changing global metadata or broader theme.

**Tech Stack:** Next.js 14, React, TypeScript, Tailwind CSS, Node.js assertion scripts for focused regression checks.

---

## File Structure

- Create: `frontend/public/deepclaw.png`
  - Static copy of the existing root-level logo asset so Next.js can serve it as `/deepclaw.png`.
- Modify: `frontend/src/components/layout/Navbar.tsx`
  - Replace the current blue `O` icon and `BaseClaw` text spans with a responsive logo image.
- Modify: `frontend/src/components/chat/ChatPanel.tsx`
  - Change the no-session welcome heading from `欢迎使用 BaseClaw` to `欢迎使用 DeepClaw`.
- Read-only reference: `deepclaw.png`
  - Source logo file at the repository root.

---

### Task 1: Add Logo Static Asset

**Files:**
- Create: `frontend/public/deepclaw.png`
- Reference: `deepclaw.png`

- [ ] **Step 1: Verify the source logo exists**

Run:

```bash
test -f /Users/wangjifei/deepexi/base-claw/deepclaw.png
```

Expected: command exits with status `0` and prints no output.

- [ ] **Step 2: Create the frontend public directory if needed**

Run:

```bash
mkdir -p /Users/wangjifei/deepexi/base-claw/frontend/public
```

Expected: command exits with status `0` and prints no output.

- [ ] **Step 3: Copy the logo into Next.js public assets**

Run:

```bash
cp /Users/wangjifei/deepexi/base-claw/deepclaw.png /Users/wangjifei/deepexi/base-claw/frontend/public/deepclaw.png
```

Expected: command exits with status `0` and prints no output.

- [ ] **Step 4: Verify the copied asset exists**

Run:

```bash
test -f /Users/wangjifei/deepexi/base-claw/frontend/public/deepclaw.png
```

Expected: command exits with status `0` and prints no output.

---

### Task 2: Replace Navbar Text Brand With Logo

**Files:**
- Modify: `frontend/src/components/layout/Navbar.tsx`

- [ ] **Step 1: Write a focused failing assertion**

Run:

```bash
node - <<'NODE'
const fs = require('fs')
const source = fs.readFileSync('/Users/wangjifei/deepexi/base-claw/frontend/src/components/layout/Navbar.tsx', 'utf8')
if (!source.includes('src="/deepclaw.png"')) {
  throw new Error('Navbar does not render /deepclaw.png')
}
if (source.includes('>BaseClaw<')) {
  throw new Error('Navbar still renders BaseClaw text')
}
if (source.includes('text-sm">O</span>')) {
  throw new Error('Navbar still renders the old O icon')
}
NODE
```

Expected: FAIL with `Navbar does not render /deepclaw.png`.

- [ ] **Step 2: Update `Navbar.tsx` imports**

Change the imports at the top of `frontend/src/components/layout/Navbar.tsx` from:

```tsx
import { ExternalLink, Menu } from 'lucide-react'
import { useApp } from '@/lib/store'
```

to:

```tsx
import Image from 'next/image'
import { Menu } from 'lucide-react'
import { useApp } from '@/lib/store'
```

- [ ] **Step 3: Replace the brand markup**

Change the brand block in `frontend/src/components/layout/Navbar.tsx` from:

```tsx
        <div className="w-8 h-8 bg-klein-blue rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-sm">O</span>
        </div>
        <span className="font-semibold text-lg text-gray-800 hidden sm:block">BaseClaw</span>
        <span className="font-semibold text-base text-gray-800 sm:hidden">BaseClaw</span>
```

to:

```tsx
        <Image
          src="/deepclaw.png"
          alt="DeepClaw"
          width={174}
          height={40}
          priority
          className="h-7 w-auto md:h-8"
        />
```

- [ ] **Step 4: Run the focused assertion again**

Run:

```bash
node - <<'NODE'
const fs = require('fs')
const source = fs.readFileSync('/Users/wangjifei/deepexi/base-claw/frontend/src/components/layout/Navbar.tsx', 'utf8')
if (!source.includes('src="/deepclaw.png"')) {
  throw new Error('Navbar does not render /deepclaw.png')
}
if (source.includes('>BaseClaw<')) {
  throw new Error('Navbar still renders BaseClaw text')
}
if (source.includes('text-sm">O</span>')) {
  throw new Error('Navbar still renders the old O icon')
}
NODE
```

Expected: PASS with no output.

---

### Task 3: Update Welcome Page Brand Text

**Files:**
- Modify: `frontend/src/components/chat/ChatPanel.tsx`

- [ ] **Step 1: Write a focused failing assertion**

Run:

```bash
node - <<'NODE'
const fs = require('fs')
const source = fs.readFileSync('/Users/wangjifei/deepexi/base-claw/frontend/src/components/chat/ChatPanel.tsx', 'utf8')
if (!source.includes('欢迎使用 DeepClaw')) {
  throw new Error('Welcome page does not use DeepClaw')
}
if (source.includes('欢迎使用 BaseClaw')) {
  throw new Error('Welcome page still uses BaseClaw')
}
NODE
```

Expected: FAIL with `Welcome page does not use DeepClaw`.

- [ ] **Step 2: Replace the welcome heading**

Change this line in `frontend/src/components/chat/ChatPanel.tsx`:

```tsx
              <div className="text-lg md:text-xl font-medium mb-2">欢迎使用 BaseClaw</div>
```

to:

```tsx
              <div className="text-lg md:text-xl font-medium mb-2">欢迎使用 DeepClaw</div>
```

- [ ] **Step 3: Run the focused assertion again**

Run:

```bash
node - <<'NODE'
const fs = require('fs')
const source = fs.readFileSync('/Users/wangjifei/deepexi/base-claw/frontend/src/components/chat/ChatPanel.tsx', 'utf8')
if (!source.includes('欢迎使用 DeepClaw')) {
  throw new Error('Welcome page does not use DeepClaw')
}
if (source.includes('欢迎使用 BaseClaw')) {
  throw new Error('Welcome page still uses BaseClaw')
}
NODE
```

Expected: PASS with no output.

---

### Task 4: Final Verification

**Files:**
- Verify: `frontend/src/components/layout/Navbar.tsx`
- Verify: `frontend/src/components/chat/ChatPanel.tsx`
- Verify: `frontend/public/deepclaw.png`

- [ ] **Step 1: Run all focused assertions together**

Run:

```bash
node - <<'NODE'
const fs = require('fs')
const navbar = fs.readFileSync('/Users/wangjifei/deepexi/base-claw/frontend/src/components/layout/Navbar.tsx', 'utf8')
const chatPanel = fs.readFileSync('/Users/wangjifei/deepexi/base-claw/frontend/src/components/chat/ChatPanel.tsx', 'utf8')
if (!fs.existsSync('/Users/wangjifei/deepexi/base-claw/frontend/public/deepclaw.png')) {
  throw new Error('frontend/public/deepclaw.png does not exist')
}
if (!navbar.includes('src="/deepclaw.png"')) {
  throw new Error('Navbar does not render /deepclaw.png')
}
if (navbar.includes('>BaseClaw<')) {
  throw new Error('Navbar still renders BaseClaw text')
}
if (navbar.includes('text-sm">O</span>')) {
  throw new Error('Navbar still renders the old O icon')
}
if (!chatPanel.includes('欢迎使用 DeepClaw')) {
  throw new Error('Welcome page does not use DeepClaw')
}
if (chatPanel.includes('欢迎使用 BaseClaw')) {
  throw new Error('Welcome page still uses BaseClaw')
}
NODE
```

Expected: PASS with no output.

- [ ] **Step 2: Run the frontend production build**

Run:

```bash
npm run build --prefix /Users/wangjifei/deepexi/base-claw/frontend
```

Expected: Next.js build completes successfully with `✓ Compiled successfully` and exits with status `0`.

- [ ] **Step 3: Check git status**

Run:

```bash
git -C /Users/wangjifei/deepexi/base-claw status --short
```

Expected: shows only intentional changes:

```text
 M frontend/src/components/layout/Navbar.tsx
 M frontend/src/components/chat/ChatPanel.tsx
?? docs/superpowers/specs/2026-05-22-logo-brand-replacement-design.md
?? docs/superpowers/plans/2026-05-22-logo-brand-replacement.md
?? frontend/public/deepclaw.png
```

- [ ] **Step 4: Commit the logo replacement**

Run:

```bash
git -C /Users/wangjifei/deepexi/base-claw add frontend/src/components/layout/Navbar.tsx frontend/src/components/chat/ChatPanel.tsx frontend/public/deepclaw.png docs/superpowers/specs/2026-05-22-logo-brand-replacement-design.md docs/superpowers/plans/2026-05-22-logo-brand-replacement.md && git -C /Users/wangjifei/deepexi/base-claw commit -m "$(cat <<'EOF'
将前端品牌标识替换为 DeepClaw logo。
EOF
)"
```

Expected: commit succeeds and reports changed files.
