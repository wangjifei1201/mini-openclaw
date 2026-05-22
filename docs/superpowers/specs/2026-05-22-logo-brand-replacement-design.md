# Logo Brand Replacement Design

## Goal

Replace the top navigation text brand `DeepClaw` with the provided logo image, and update the welcome page brand text from `DeepClaw` to `DeepClaw`.

## Scope

- Use the existing root-level `deepclaw.png` asset as the frontend logo.
- Make the asset available to Next.js by copying it to `frontend/public/deepclaw.png`.
- Update `frontend/src/components/layout/Navbar.tsx` so the left-side brand area renders the logo image instead of the blue `O` icon and `DeepClaw` text.
- Update `frontend/src/components/chat/ChatPanel.tsx` so the empty welcome state says `欢迎使用 DeepClaw`.

## Layout

The navbar height remains `h-14`. The logo should fit inside the current header without increasing its height. Use a fixed display height around 28-32px and auto width so the original logo aspect ratio is preserved. The logo should remain visible on both desktop and mobile.

## Out of Scope

- Browser metadata title remains unchanged unless requested separately.
- No favicon changes.
- No broader theme or color changes.

## Verification

- Run a focused assertion that the navbar references `/deepclaw.png` and no longer renders `DeepClaw` in the navbar.
- Run a focused assertion that the welcome text uses `DeepClaw`.
- Run the frontend production build.
