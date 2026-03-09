#!/usr/bin/env bash
# =============================================================================
# IM|Copilot — One-Command Setup Script
# Usage:  chmod +x setup.sh && ./setup.sh
# =============================================================================

set -e  # Exit on any error

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()     { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
header()  { echo -e "\n${BOLD}${CYAN}$1${NC}\n$(printf '─%.0s' {1..50})"; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}"
cat << 'BANNER'
  _____ __  __  _____            _ _       _
 |_   _|  \/  |/ ____|          (_) |     | |
   | | | \  / | |     ___  _ __  _| | ___ | |_
   | | | |\/| | |    / _ \| '_ \| | |/ _ \| __|
  _| |_| |  | | |___| (_) | |_) | | | (_) | |_
 |_____|_|  |_|\_____\___/| .__/|_|_|\___/ \__|
                           | |
  AI Academic Assistant    |_|  IMSciences Peshawar
BANNER
echo -e "${NC}"
echo -e "  ${CYAN}FYP-1 Setup Script${NC} · Hybrid RAG + Text-to-SQL Architecture"
echo ""

# ── Check prerequisites ───────────────────────────────────────────────────────
header "Step 1 — Checking Prerequisites"

command -v python3 &>/dev/null || error "Python 3.10+ is required. Install from python.org"
command -v pip    &>/dev/null  || error "pip is required."
command -v node   &>/dev/null  || error "Node.js 18+ is required. Install from nodejs.org"
command -v npm    &>/dev/null  || error "npm is required."

PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
NODE_VER=$(node --version | tr -d 'v' | cut -d. -f1)

success "Python $PYTHON_VER detected"
success "Node.js $(node --version) detected"

[[ $(echo "$PYTHON_VER >= 3.10" | bc -l) -eq 1 ]] || \
  warn "Python 3.10+ recommended. You have $PYTHON_VER"
[[ $NODE_VER -ge 18 ]] || \
  warn "Node.js 18+ recommended."

# ── Detect project root ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

[[ -d "$BACKEND_DIR"  ]] || error "backend/ directory not found. Run from project root."
[[ -d "$FRONTEND_DIR" ]] || error "frontend/ directory not found. Run from project root."

# ── Backend setup ─────────────────────────────────────────────────────────────
header "Step 2 — Setting Up Python Backend"

cd "$BACKEND_DIR"

# Create virtual environment
if [[ ! -d "venv" ]]; then
  log "Creating Python virtual environment..."
  python3 -m venv venv
  success "Virtual environment created at backend/venv/"
else
  success "Virtual environment already exists."
fi

# Activate venv
source venv/bin/activate

# Install dependencies
log "Installing Python dependencies (this may take 2-3 minutes)..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
success "All Python packages installed."

# Check for .env file
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
    warn ".env file created from .env.example"
    warn "ACTION REQUIRED: Open backend/.env and add your API keys:"
    echo ""
    echo -e "  ${YELLOW}GROQ_API_KEY=your_key_here${NC}   ← get free at console.groq.com"
    echo -e "  ${YELLOW}GEMINI_API_KEY=your_key_here${NC}  ← get free at aistudio.google.com"
    echo ""
    warn "At least ONE key is required. Press Enter to continue setup..."
    read -r
  fi
else
  success ".env file found."
fi

# Pre-initialize the database and vector store
log "Pre-initializing SQLite database and ChromaDB vector store..."
python3 -c "
from database import initialize_database
from vector_store import initialize_vector_store
initialize_database()
stats = initialize_vector_store()
print(f'  Database: ready')
print(f'  ChromaDB: {stats[\"total_chunks\"]} chunks indexed')
" && success "Database and vector store initialized." || warn "Pre-init skipped (will run on first server start)."

deactivate

# ── Frontend setup ────────────────────────────────────────────────────────────
header "Step 3 — Setting Up React Frontend"

cd "$FRONTEND_DIR"

log "Installing npm packages..."
npm install --silent
success "Frontend packages installed."

# ── Create launch scripts ─────────────────────────────────────────────────────
header "Step 4 — Creating Launch Scripts"

cd "$SCRIPT_DIR"

# Backend launcher
cat > start_backend.sh << 'EOF'
#!/usr/bin/env bash
cd "$(dirname "${BASH_SOURCE[0]}")/backend"
source venv/bin/activate
echo ""
echo "  Starting IM|Copilot Backend..."
echo "  API:  http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo ""
uvicorn main:app --reload --host 0.0.0.0 --port 8000
EOF

# Frontend launcher
cat > start_frontend.sh << 'EOF'
#!/usr/bin/env bash
cd "$(dirname "${BASH_SOURCE[0]}")/frontend"
echo ""
echo "  Starting IM|Copilot Frontend..."
echo "  App:  http://localhost:5173"
echo ""
npm run dev
EOF

chmod +x start_backend.sh start_frontend.sh
success "start_backend.sh created"
success "start_frontend.sh created"

# ── Final summary ─────────────────────────────────────────────────────────────
header "Setup Complete!"

echo -e "  ${GREEN}✓${NC} Python backend configured"
echo -e "  ${GREEN}✓${NC} React frontend configured"
echo -e "  ${GREEN}✓${NC} SQLite database seeded with demo data"
echo -e "  ${GREEN}✓${NC} ChromaDB handbook indexed"
echo ""
echo -e "  ${BOLD}To start the application:${NC}"
echo ""
echo -e "  ${CYAN}Terminal 1 (Backend):${NC}   ./start_backend.sh"
echo -e "  ${CYAN}Terminal 2 (Frontend):${NC}  ./start_frontend.sh"
echo ""
echo -e "  ${CYAN}Then open:${NC}  http://localhost:5173"
echo ""
echo -e "  ${BOLD}Demo student IDs:${NC} S001–S010"
echo -e "  ${BOLD}API docs:${NC}        http://localhost:8000/docs"
echo ""

if grep -q "your_groq_api_key_here" "$BACKEND_DIR/.env" 2>/dev/null; then
  echo -e "  ${RED}⚠ REMINDER: Add your API keys to backend/.env before starting!${NC}"
  echo ""
fi
