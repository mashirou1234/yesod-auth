---
version: alpha
name: yesod-auth Admin Surface
description: Lightweight admin and tour UI identity for authentication demos, Streamlit admin screens, and browser guidance overlays.
colors:
  background: "#F8FAFC"
  surface: "#FFFFFF"
  primary: "#2563EB"
  primary-strong: "#1D4ED8"
  text: "#0F172A"
  text-muted: "#475569"
  border: "#CBD5E1"
  focus: "#DBEAFE"
  shadow: "#0F172A"
typography:
  body-md:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.7
  button-label:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.2
  title:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 18px
    fontWeight: 700
    lineHeight: 1.35
rounded:
  sm: 8px
  md: 14px
  full: 999px
spacing:
  sm: 8px
  md: 16px
  lg: 24px
components:
  tour-launcher:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.full}"
    padding: 12px
  tour-popover:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
  focus-ring:
    backgroundColor: "{colors.focus}"
    textColor: "{colors.primary-strong}"
---

## Overview

yesod-auth の visual surface は、認証フロー、admin 画面、browser tour の補助 UI を中心にする。主 UI は軽量で、認証状態や操作説明を妨げないことを優先する。

## Colors

既存 tour launcher の blue を primary とし、white surface と slate text を基準にする。focus ring は blue の低 opacity とし、アクセシビリティ上の視認性を確保する。

## Typography

system UI font を使う。tour title は 18px、description と button は 14px を基準にし、狭い admin 画面でも読みやすくする。

## Layout

launcher は右下固定、popover は 420px 以下を目安にする。Streamlit admin 画面では標準コンポーネントを尊重し、独自装飾は導線補助に限定する。

## Elevation & Depth

launcher と popover は軽い shadow で前面性を示す。認証画面の主操作より tour 装飾が目立ちすぎないようにする。

## Shapes

launcher は capsule、popover は 14px 角丸を基準にする。入力や admin 表示はプラットフォーム標準に合わせる。

## Components

tour launcher、tour popover、focus ring、admin metric block を基準にする。

## Do's and Don'ts

- Do: 認証状態、権限、エラーは文言で明示する。
- Do: tour overlay は既存画面の操作を隠しすぎない。
- Don't: 認証フローに不要な装飾や複雑な motion を入れない。
- Don't: 色だけで安全/危険/完了を表現しない。
