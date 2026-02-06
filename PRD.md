# Perfect ASIN - Product Requirements Document v2.0

**AI-Powered Amazon Listing Carousel Optimization Tool**

> "Generate conversion-optimized product image carousels in minutes, not days."

| Field | Value |
|-------|-------|
| Document Version | 2.0 |
| Date | January 3, 2026 |
| Status | Ready for Development |
| Product Name | Perfect ASIN |
| Domain | PerfectASIN.com |
| Tech Stack | Google Cloud Platform (Vertex AI, Gemini 2.5, Imagen 4) |
| Primary Goal | Increase Amazon Listing Conversion Rates |

---

## 1. Executive Summary

### 1.1 Product Overview

Perfect ASIN is an AI-powered SaaS platform that generates complete, conversion-optimized Amazon product image carousels (7-9 images) from minimal user input. The system analyzes existing Amazon listings, extracts product data automatically, studies top-performing competitors, and generates professional carousel images designed to maximize buyer conversion rates.

### 1.2 Core Value Proposition

- **15-minute carousel generation** vs. 1-3 weeks with traditional methods
- **Zero design skills required** - AI handles all creative decisions
- **Automatic competitor analysis** and best-practice extraction
- **100% Amazon-compliant output** (dimensions, format, content guidelines)
- **Zero spelling/grammar errors** through multi-layer text validation
- **ICP-optimized copy** written in proper American English

### 1.3 Key Differentiators

| Feature | Competitors | Perfect ASIN |
|---------|-------------|--------------|
| ASIN Auto-Extraction | Manual input only | Auto-scrape from URL/ASIN |
| Competitor Analysis | None or basic | Top 10 SERP analysis |
| Text Validation | Basic spell-check | Multi-layer AI + dictionary |
| Image Themes | Generic templates | 7 conversion-optimized themes |
| ICP Optimization | User-defined only | AI-suggested + user override |
| Output Quality | Varies | 2000x2000px PNG guaranteed |

---

## 2. Product Vision & Goals

### 2.1 Mission Statement

Empower Amazon sellers of all sizes to create professional, high-converting product image carousels without design expertise, expensive agencies, or lengthy turnaround times. Our north star metric is **increasing listing conversion rates** for every user.

### 2.2 Primary Business Goals

1. Reduce carousel creation time from weeks to under 15 minutes
2. Achieve measurable conversion rate improvements for users (target: 15-30% lift)
3. Maintain zero-tolerance policy on spelling/grammar errors
4. Scale to 10,000+ monthly active users within Year 1
5. Achieve 99% Amazon compliance rate on generated images

### 2.3 Target Users

| User Segment | Characteristics | Primary Needs |
|--------------|-----------------|---------------|
| Solo Sellers | 1-10 products, limited budget | Speed, affordability, no design skills required |
| Growing Brands | 10-100 products, small team | Consistency, bulk generation, brand guidelines |
| Agencies | Manage multiple client accounts | White-label options, client management, API access |
| Enterprise Sellers | 100+ products, established | Integration, compliance, audit trails |

---

## 3. User Input Specifications

### 3.1 Product Identification (Required)

| Field | Type | Functionality |
|-------|------|---------------|
| **Amazon ASIN*** | Text (10 chars) OR Full URL | Primary identifier. User can paste full Amazon URL or just ASIN. System extracts and fetches all product data. |
| **Main Product Photo*** | File Upload (PNG/JPG, max 15MB, min 1000x1000px) | High-res product image. Transparent background PNG preferred. System auto-removes background if needed. |
| **Additional Photos** | File Upload (up to 5) | Optional angles, packaging shots for carousel variations. |

### 3.2 Product Details (Auto-Populated from ASIN)

These fields auto-populate when ASIN is provided but can be manually edited:

| Field | Type | Source |
|-------|------|--------|
| Product Title* | Text (max 200 chars) | Extracted from PDP |
| Brand Name* | Text (max 100 chars) | Extracted from brand field |
| Product Category | Dropdown (auto-detected) | Amazon category hierarchy |
| Key Features/Benefits* | Multi-line (5-10 items) | Extracted from bullet points |
| Price | Currency + Number | Current listing price |
| Star Rating | Number (1.0-5.0) | Current average rating |
| Review Count | Number | Total reviews |
| Product Description | Text Area (max 2000 chars) | A+ content or description |

### 3.3 Keywords

| Field | Type | Functionality |
|-------|------|---------------|
| **Primary Keyword*** | Text (max 100 chars) | Main search term. Used for SERP competitor analysis (Top 10 organic). |
| Secondary Keywords | Multi-line (up to 5) | Additional terms for copy generation and feature prioritization. |

### 3.4 Brand & Style Configuration

| Field | Type | Options |
|-------|------|---------|
| Brand Identity & Style | Text Area (max 300 chars) | Example: "Modern minimalist, earth tones, targets millennial moms" |
| Visual Theme Preset | Dropdown | Clean/Minimal, Rustic/Artisan, Bold/Aggressive, Organic/Natural, Premium/Luxury, Fun/Playful, Technical/Professional |
| Primary Brand Color | Color Picker (HEX) | Main accent color |
| Secondary Brand Color | Color Picker (HEX) | Supporting color |
| Brand Logo | File Upload (PNG/SVG) | Optional, for lifestyle images |

### 3.5 Target Audience

| Field | Type | Functionality |
|-------|------|---------------|
| Target Audience | Text Area OR "AI Suggest" | Example: "Health-conscious women 25-45". AI suggests 3 ICPs if blank. |
| Use AI Suggestions | Toggle (On/Off) | AI analyzes product + category + competitors for ICP options. |
| Competitor ASINs | Text (up to 5) | Optional specific competitors. Defaults to Top 10 organic. |

---

## 4. ASIN Data Extraction Engine

### 4.1 Input Methods

1. Direct ASIN entry (e.g., B08XYZ123)
2. Full Amazon URL (e.g., https://www.amazon.com/dp/B08XYZ123)
3. Amazon URL with referral parameters (auto-cleaned)
4. International domains (.co.uk, .de, .ca, etc.)

### 4.2 Data Points Extracted

| Category | Fields | Usage |
|----------|--------|-------|
| Basic Info | Title, Brand, ASIN, Category | Pre-populate form, template selection |
| Pricing | Current price, List price, Deal status | Value messaging, variant displays |
| Features | Bullet points (5-7) | Auto-populate benefits, infographic content |
| Description | Product description, A+ content | Feature mining, copy inspiration |
| Social Proof | Star rating, Review count, BSR | Social proof images, trust badges |
| Specifications | Dimensions, Weight, Materials | Size comparison images, spec infographics |
| Images | Existing carousel URLs | Style analysis, gap identification |
| Variations | Size/Color options, Pricing | Variant comparison images |

### 4.3 Technical Implementation

- **Primary**: Amazon Product Advertising API (PA-API 5.0)
- **Fallback**: Headless browser scraping (Puppeteer/Playwright)
- **Rate Limiting**: Request throttling for Amazon ToS compliance
- **Caching**: 24-hour cache to reduce API calls
- **Error Handling**: Graceful degradation; allow manual entry

---

## 5. Carousel Image Templates (7 Slots)

### Slot 1: Hero/Main Image
- **Purpose**: First impression. Must meet Amazon's strict requirements.
- **Requirements**: Pure white background (#FFFFFF), product fills 85%+, no text/logos
- **AI Focus**: Clean cutout, professional studio lighting, optional loose product display

### Slot 2: Lifestyle/Origin Image
- **Purpose**: Establish authenticity, origin story, brand credibility
- **Elements**: Product arranged artistically, trust badges, benefit icons
- **Text Overlay**: Headline + 3-4 benefit icons with labels
- **Example**: "AUTHENTIC MEXICAN ANCHO CHILES" with Mexico flag, All Natural, Farm Fresh icons

### Slot 3: Feature Infographic (Flavor/Specs)
- **Purpose**: Communicate key attributes in visual format
- **Elements**: Product + infographic wheel/chart, visual scales
- **Text Overlay**: Headline + attribute labels + metrics
- **Example**: Flavor wheel (Chocolate Notes, Sweet Raisin, Mild Heat, Smoky Finish) + Scoville scale

### Slot 4: How-To-Use / Instructions
- **Purpose**: Reduce purchase hesitation with clear usage guidance
- **Elements**: 3-5 numbered steps, action photos/icons, pro tip callout
- **Text Overlay**: Headline + step titles + brief instructions
- **Example**: 4-step process with Pro Tip footer

### Slot 5: Size & Scale / Variant Comparison
- **Purpose**: Set accurate expectations, showcase variants, highlight value
- **Elements**: Product with ruler, multiple size variants, "Best Value" badge
- **Text Overlay**: Headline + quantity info + pricing + availability
- **Example**: Ruler measurement + 3 package sizes with prices

### Slot 6: Use Cases / Recipe Ideas
- **Purpose**: Inspire purchase by showing versatility
- **Elements**: 6 application photos in 2x3 grid, circular frames
- **Text Overlay**: Headline + application labels + tagline
- **Example**: Chili, Mole, Enchiladas, Salsa, Tacos, Stews grid

### Slot 7: Social Proof / Quality Guarantee
- **Purpose**: Build trust, reduce risk, reinforce quality
- **Elements**: Brand logo, 5 trust badges (numbered), star rating
- **Text Overlay**: Headline + badge labels + satisfaction promise
- **Example**: "PREMIUM QUALITY GUARANTEE" with 5 circular badges + 4.7/5 stars

---

## 6. AI Image Generation Pipeline

### 6.1 Three-Layer Composition (Critical Architecture)

**Problem**: AI image generators struggle with accurate text rendering.

**Solution**: Separate generation from text overlay:

1. **Layer 1 - Background/Scene**: AI-generated (Imagen 4)
2. **Layer 2 - Product Image**: User upload (background removed)
3. **Layer 3 - Text & Graphics**: Programmatic rendering (100% accuracy)

### 6.2 Google Vertex AI Models

| Component | Model | Purpose |
|-----------|-------|---------|
| Scene Generation | Imagen 4 (imagen-4.0-generate-001) | Backgrounds, lifestyle scenes |
| Premium Generation | Imagen 4 Ultra | Hero images, key shots |
| Copy Generation | Gemini 2.5 Flash | Headlines, ICP-optimized copy |
| Image Analysis | Gemini 2.5 Flash (Multimodal) | Analyze uploads, suggest compositions |
| Competitor Analysis | Gemini 2.5 Pro | Deep competitor strategy analysis |

### 6.3 Imagen 4 Configuration

```python
config = {
    "model": "imagen-4.0-generate-001",
    "image_size": "2K",  # 2048x2048
    "aspect_ratio": "1:1",
    "number_of_images": 4,
    "safety_filter_level": "block_some",
    "person_generation": "allow_adult",
    "language": "en"
}
```

### 6.4 Composition Pipeline

1. **Background Generation**: Imagen generates scene from slot template
2. **Product Extraction**: Remove background (rembg or Cloud Vision)
3. **Shadow Generation**: AI-generate realistic shadow/reflection
4. **Composite Assembly**: Layer product onto background
5. **Text Overlay Rendering**: Python Pillow or HTML5 Canvas
6. **Final Export**: 2000x2000px PNG, optimized file size

---

## 7. Quality Control & Text Validation

### 7.1 Multi-Layer Validation Pipeline

| Layer | Method | Purpose |
|-------|--------|---------|
| 1 | Gemini Spell Check | AI contextual spelling/grammar |
| 2 | LanguageTool API | Rule-based grammar, style |
| 3 | PySpellChecker | Dictionary-based fallback |
| 4 | Brand Dictionary | Whitelist brand names, jargon |
| 5 | Human Review Flag | Flag uncertain corrections |

### 7.2 American English Rules

- Default American spelling (color, flavor)
- American idioms natural to target ICP
- Support UK, CA, AU as selectable options
- ICP-appropriate vocabulary level

### 7.3 Copy Generation Prompt

```
You are an expert Amazon copywriter.

Product: {product_name}
Category: {category}
Key Benefits: {benefits}
Target Audience (ICP): {icp}

Task: Generate {count} headlines (max 4-5 words each).

RULES:
1. Use proper American English spelling and grammar
2. Zero spelling errors - double-check every word
3. Match tone to ICP: {tone}
4. Use action words and benefit-focused language
5. Avoid generic phrases like "Best Quality"
6. Include power words: Premium, Authentic, Fresh, Natural
7. Create urgency or aspiration where appropriate
```

### 7.4 Post-Generation Verification

1. **OCR Verification**: Cloud Vision extracts rendered text
2. **Compare**: Verify OCR matches intended text
3. **Flag Discrepancies**: Regenerate if mismatch
4. **Quality Score**: Target 99.9% accuracy

---

## 8. Technical Architecture

### 8.1 Google Cloud Platform Stack

| Component | Service | Purpose |
|-----------|---------|---------|
| Image Generation | Vertex AI - Imagen 4 | AI image generation |
| Text/Logic AI | Vertex AI - Gemini 2.5 | Copy, ICP, competitors |
| Vision/OCR | Cloud Vision API | Text verification |
| Backend API | Cloud Run | FastAPI, auto-scaling |
| Frontend | Firebase Hosting | React.js with CDN |
| Database | Cloud Firestore | Users, projects, history |
| File Storage | Cloud Storage | Images, assets, exports |
| Authentication | Firebase Auth | User accounts, OAuth |
| Job Queue | Cloud Tasks | Async processing |
| Monitoring | Cloud Monitoring | Metrics, errors |
| Secrets | Secret Manager | API keys |

### 8.2 Architecture Flow

```
[Browser] → [Firebase Hosting (React)]
                ↓
        [Cloud Run API (FastAPI)]
                ↓
    ┌─────────────────────────┐
    │      Vertex AI          │
    │  Imagen 4 | Gemini 2.5  │
    └─────────────────────────┘
                ↓
    [Cloud Storage] ↔ [Firestore]
                ↓
    [Generated Images] → [User Export]
```

---

## 9. User Interface Design

### 9.1 Dashboard Layout

- **Left Panel (25%)**: Input form with collapsible sections
- **Right Panel (75%)**: Live preview grid (7 carousel images)
- **Top Bar**: Project name, Save, Export buttons

### 9.2 Preview Grid Features

- Hero image larger at top
- 6 supporting images in 2x3 grid with labels
- Thumbnail carousel below each (3-4 AI variations)
- Action buttons: Edit, Download, Upload, Regenerate
- Drag & drop to reorder

### 9.3 Image Editor Modal

- Canvas preview with editable text layers
- Click text to edit (font/size/color controls)
- Background swap (regenerate background only)
- Product repositioning (drag to adjust)
- Save/Cancel buttons

---

## 10. Output Specifications

### 10.1 Technical Requirements

| Spec | Requirement |
|------|-------------|
| Primary Resolution | 2000 x 2000 pixels |
| Minimum Acceptable | 1000 x 1000 pixels |
| File Format | PNG (primary), JPEG (compressed) |
| Color Space | sRGB |
| File Size | < 5MB per image |
| Hero Background | Pure white (#FFFFFF) |
| Text Legibility | Min 14pt at 1000px view |

### 10.2 Export Package (ZIP)

```
perfectasin_carousel_[ASIN]/
├── 01_Hero_Main.png
├── 02_Lifestyle_Origin.png
├── 03_Infographic_Features.png
├── 04_HowToUse.png
├── 05_Size_Scale.png
├── 06_UseCases_Recipes.png
├── 07_SocialProof_Guarantee.png
└── README.txt (upload instructions)
```

---

## 11. Competitive Analysis Integration

### 11.1 SERP Analysis

1. Fetch Top 10 ASINs for primary keyword
2. Extract carousel images from each
3. Analyze image types used
4. Identify common themes/colors
5. Extract text overlays and headlines
6. Generate "Best Practices" report

### 11.2 Intelligence Output

- Image Type Distribution: "7/10 competitors use How-To-Use"
- Color Trends: "Dominant: Red (80%), Earth tones (60%)"
- Trust Badge Usage: "Average 4.2 badges per carousel"
- Gap Opportunities: "Only 2 show recipes - differentiation opportunity"

---

## 12. Development Roadmap

### Phase 1: MVP (8 Weeks)

- Week 1-2: GCP setup, Vertex AI integration, API scaffolding
- Week 3-4: ASIN extraction, form UI, database schema
- Week 5-6: Imagen integration, prompts, 3-layer composition
- Week 7: Text validation, spell-check pipeline
- Week 8: Export, QA, beta launch

### Phase 2: Enhanced (4 Weeks)

- SERP competitive analysis
- Advanced image editor
- AI-suggested ICP profiles
- Additional theme presets

### Phase 3: Scale (4 Weeks)

- Subscription billing (Stripe)
- Bulk generation
- API access
- White-label options

---

## 13. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Generation Time | < 15 minutes | ASIN input to export |
| Spelling Errors | < 0.01% | OCR verification |
| Amazon Compliance | > 99% | Validator pass rate |
| User Satisfaction | NPS > 50 | Post-generation survey |
| Completion Rate | > 85% | Full 7-image carousel |
| Conversion Lift | 15-30% | User-reported before/after |
| MAU (Year 1) | > 5,000 | Analytics |
| CAC | < $50 | Marketing / new users |

---

## Appendix: Key Prompts

### ICP Generation

```
You are an expert Amazon marketing strategist.

Product: {product_name}
Category: {category}
Price: {price}
Features: {features}

Generate 3 distinct ICPs with:
1. Persona Name
2. Demographics
3. Psychographics
4. Primary Pain Point
5. Purchase Motivator

Format: JSON array
```

### Headline Generation

```
You are an expert Amazon listing copywriter.

Product: {product_name}
ICP: {selected_icp}
Image Type: {slot_type}

Generate 5 headlines (max 5 words each).

RULES:
- American English
- Action-oriented
- Zero spelling errors
- Match ICP tone
```

---

*End of Document*

**Perfect ASIN** | PerfectASIN.com | PRD v2.0 | January 2026
