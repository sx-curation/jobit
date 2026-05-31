# Design System Specification

## 1. Overview & Creative North Star: "The Kinetic Archive"
This design system moves away from the sterile, boxed-in nature of traditional SaaS platforms. Instead, it embraces the philosophy of **"The Kinetic Archive"**—a high-end editorial approach to data management. 

While the system handles dense information (job titles, companies, salaries), it treats every entry as a curated record. By utilizing aggressive whitespace, intentional asymmetry in layouts, and a total rejection of traditional 1px borders, we create an interface that feels fluid and premium. The goal is to make the user feel like a talent executive, not a data entry clerk. We achieve this through "breathable density"—where information is packed tight, but the containers themselves have room to float.

---

## 2. Colors: Chromatic Depth & Tonal Layering
Our palette is anchored by the stability of **LinkedIn Blue (`primary`)** and the crispness of the **#F8F9FA background**. 

### The "No-Line" Rule
Standard UI relies on borders to separate content. This design system prohibits them. Sections must be defined through background shifts. For example:
- **Base Layer:** `surface` (#F8F9FA).
- **Secondary Content Area:** `surface-container-low` (#F3F4F5).
- **Interactive Cards:** `surface-container-lowest` (#FFFFFF).

### Surface Hierarchy & Nesting
To create a sense of physical organization, we use tonal nesting. A job application detail view should be a `surface-container-high` sheet sliding over the main `surface` dashboard. Each layer deeper into the application should utilize a slightly higher tier of surface color (moving toward `surface-bright`), creating an organic sense of "lifting" toward the user.

### Glass & Gradient Rule
To ensure the UI feels custom and not "out-of-the-box":
- **Floating Modals/Nav:** Use a semi-transparent `surface` color with a `backdrop-filter: blur(20px)`.
- **Signature CTAs:** Primary buttons and "Applied" status indicators should utilize a subtle linear gradient from `primary` (#005D8F) to `primary_container` (#0077B5) at a 135-degree angle. This adds "soul" and visual weight that flat colors lack.

---

## 3. Typography: The Editorial Balance
We utilize a triad of typefaces to establish authority and technical precision.

*   **Display & Headlines (Manrope):** This is our "Voice." Used for page headers and large statistics. It is bold, modern, and high-contrast.
*   **Body & Utility (Inter):** Our "Workhorse." Inter provides maximum legibility for company names, job descriptions, and table data.
*   **Labels & Tags (Space Grotesk):** Our "Signature." By using a technical monospace-adjacent font for status tags (`label-md`), we ground the editorial look with a sense of "system-generated" accuracy.

**Typographic Hierarchy Note:** High-end design thrives on scale contrast. Pair a `display-lg` number (e.g., "42 Applications") directly above a `label-sm` monospace tag ("TOTAL_VOLUME") to create a sophisticated, data-driven aesthetic.

---

## 4. Elevation & Depth: Tonal Sophistication
Shadows and borders are replaced by **Tonal Layering**.

*   **The Layering Principle:** Rather than using a drop shadow to show a card is clickable, change the surface from `surface-container-lowest` to `surface-container-high` on hover.
*   **Ambient Shadows:** For "floating" elements like popovers, use an ultra-diffused shadow:
    - *Y: 20px, Blur: 40px, Color: rgba(25, 28, 29, 0.06)* (using a tinted version of `on-surface`).
*   **The "Ghost Border" Fallback:** If accessibility requires a container edge, use the `outline-variant` token at 15% opacity. It should be felt, not seen.

---

## 5. Components: Refined Utility

### Buttons & Controls
*   **Primary Button:** Gradient fill (`primary` to `primary_container`), `full` rounded corners, and `title-sm` (Inter) typography. 
*   **Segmented Controls:** These should look like "carved" paths in the UI. Use a `surface-container-highest` track with a `surface-container-lowest` thumb that carries a 4% ambient shadow.
*   **Pill Badges:** Use `full` roundedness and `label-md` (Space Grotesk). For status-specific colors:
    - **Applied:** `secondary_container` background with `on_secondary_container` text.
    - **Interviewing:** `tertiary_fixed` background with `on_tertiary_fixed` text.

### Data Tables (The "Dense List")
*   **Structure:** No vertical or horizontal lines. 
*   **Row Styling:** Alternate background colors using `surface` and `surface-container-low`. 
*   **Interaction:** On hover, the row should shift to `primary_fixed` at 30% opacity to highlight the selection without obscuring data.
*   **Text Alignment:** Monospace `label-md` for dates and salary figures to ensure perfect vertical alignment across rows.

### Input Fields
Avoid the "boxy" look. Use a `surface-container-high` background with a 2px bottom-only border in `outline-variant`. On focus, the bottom border animates to `primary` and the background shifts to `surface-container-lowest`.

---

## 6. Do's and Don'ts

### Do
*   **DO** use whitespace as a structural element. A 48px gap between sections is more effective than a line.
*   **DO** use "Space Grotesk" for all metadata (tags, dates, IDs). It signals that the data is live and accurate.
*   **DO** nest `surface-container-lowest` cards within a `surface-container-low` background to create soft depth.

### Don't
*   **DON'T** use 100% black text. Always use `on-surface` (#191C1D) for better optical comfort.
*   **DON'T** use standard 4px or 8px border radii. This system requires the high-end look of `DEFAULT` (1rem) or `full` for a modern, fluid feel.
*   **DON'T** ever use a solid 1px border to separate the sidebar from the main content. Use a background color shift.

### Accessibility Note
While we prioritize tonal shifts, ensure the contrast ratio between `on-surface` and all `surface` variants meets WCAG AA standards. When in doubt, use the **Ghost Border** fallback for interactive elements.