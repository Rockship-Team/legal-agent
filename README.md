# Legal Chatbot

Vietnamese Legal Chatbot with AI-powered contract generation and legal research.

## Features

- **Legal Research**: Search and analyze Vietnamese laws from thuvienphapluat.vn
- **Interactive Contract Creation**: Step-by-step contract creation with Q&A
- **Universal PDF Export**: Generate professional PDF contracts with full Vietnamese support
- **Claude Code Integration**: Use slash commands for seamless workflow

## Requirements

- Python 3.11+
- Claude Code CLI

## Installation

```bash
# Clone repo
git clone https://github.com/Rockship-Team/chatbot.git
cd chatbot

# Setup Python environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e .
```

## Usage with Claude Code

### Slash Commands (Recommended)

| Command | Description |
|---------|-------------|
| `/legal.create-contract` | Create contract interactively with legal research |
| `/legal.export-pdf` | Export current contract to PDF |
| `/legal.preview` | Preview contract in browser |
| `/legal.research` | Research Vietnamese laws on any topic |
| `/legal.help` | Show all available commands |

### Example Workflow

```bash
# 1. Create a rental contract
/legal.create-contract thue nha

# 2. Answer questions step-by-step
# Bot will research laws from thuvienphapluat.vn first

# 3. Export to PDF
/legal.export-pdf

# 4. Or preview in browser
/legal.preview
```

### Direct PDF Generation

```bash
# Generate PDF from existing JSON contract
python -m legal_chatbot.services.pdf_generator data/contracts/contract.json
```

## Project Structure

```
legal_chatbot/
├── services/
│   ├── pdf_generator.py   # Universal PDF generator
│   ├── crawler.py         # Web crawler for thuvienphapluat.vn
│   └── generator.py       # Template-based generator
├── models/                # Pydantic models
├── utils/
│   ├── pdf_fonts.py       # Vietnamese font support
│   └── vietnamese.py      # Text processing
└── templates/             # Contract templates (JSON)

data/
└── contracts/             # Generated contracts (JSON + PDF)

.claude/
└── commands/              # Slash command definitions
    ├── legal.create-contract.md
    ├── legal.export-pdf.md
    ├── legal.preview.md
    └── legal.research.md
```

## Supported Contract Types

| Type | Vietnamese | Legal Basis |
|------|------------|-------------|
| `rental` | Hop dong thue nha | Luat Nha o 2014 |
| `sale_land` | Hop dong chuyen nhuong dat | Luat Dat dai 2024 |
| `sale_house` | Hop dong mua ban nha | Bo luat Dan su 2015 |
| `employment` | Hop dong lao dong | Bo luat Lao dong 2019 |
| `service` | Hop dong dich vu | Bo luat Dan su 2015 |

## Tech Stack

- **PDF Generation**: ReportLab with Vietnamese fonts (Times New Roman)
- **Legal Research**: Web scraping from thuvienphapluat.vn
- **CLI Integration**: Claude Code slash commands

## Disclaimer

This chatbot provides legal information for reference purposes only. It does not constitute legal advice and should not be used as a substitute for professional legal consultation.

## License

MIT
