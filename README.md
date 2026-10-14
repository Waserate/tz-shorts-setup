# TZ Shorts Setup

ชุดติดตั้งเครื่องสำหรับตัด Shorts ของช่อง **Take A Zeat / Bangkok Esports** ด้วย Claude + CapCut
รัน `setup.ps1` ครั้งเดียว แล้วโปรแกรม เครื่องมือ Skill และ Plugin ทั้งหมดในตารางด้านล่างจะถูกติดตั้งให้เอง

---

## วิธีติดตั้ง (ทำครั้งเดียว)

1. **ดาวน์โหลด repo นี้**
   - วิธีง่าย: บนหน้า GitHub กดปุ่มสีเขียว **Code → Download ZIP** แล้วแตกไฟล์ไว้ที่ไหนก็ได้ เช่น `C:\Users\<ชื่อคุณ>\tz-shorts-setup`
   - หรือถ้ามี Git แล้ว: `git clone https://github.com/<owner>/tz-shorts-setup`
2. **เปิด PowerShell ในโฟลเดอร์นั้น** (คลิกขวาในโฟลเดอร์ → *Open in Terminal*) แล้วพิมพ์
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup.ps1
   ```
   - ใช้เวลาประมาณ 20–60 นาที ขึ้นกับเน็ต (ช่วงที่โหลดนานที่สุดคือโมเดล Whisper ขนาด 2.9 GB)
   - ถ้ามีหน้าต่างขอสิทธิ์ (UAC) เด้งขึ้นมา ให้กด **Yes**
   - ถ้าไม่อยากโหลดโมเดล Whisper ให้เติม `-SkipModel` ต่อท้ายคำสั่ง
   - รันซ้ำได้ไม่มีปัญหา ตัวที่ติดตั้งแล้วจะถูกข้ามไป
3. ดูตาราง **SUMMARY** ตอนจบ ถ้ามีบรรทัดไหนขึ้น `FAIL` ให้ส่งไฟล์ `setup.log` ให้พี่ หรือแปะให้ Claude อ่าน
4. **ล็อกอินเอง** (สคริปต์ล็อกอินแทนไม่ได้)
   1. VS Code → แผง Claude → Sign in ด้วยบัญชี Claude ของตัวเอง
   2. เปิด CapCut 1 ครั้ง แล้วล็อกอิน
   3. พิมพ์ `notebooklm login` แล้วล็อกอิน Google (ใช้สำหรับดึง transcript YouTube)
   4. `gh auth login` (ทำเฉพาะเมื่อต้องการดึงอัปเดตของ repo นี้)
5. ถ้าตอนแรกขั้น *CapCut donor drafts* หรือ *Claude plugins* FAIL ให้ทำข้อ 4 ก่อน แล้วรัน `setup.ps1` ซ้ำอีกรอบ

---

## setup.ps1 ติดตั้งอะไรบ้าง

### 1. โปรแกรมหลัก (ติดตั้งผ่าน winget)

| โปรแกรม | ติดตั้งด้วย | มีไว้ทำอะไร |
|---|---|---|
| **Git for Windows** | `winget install Git.Git` | Claude Code บน Windows ต้องมีตัวนี้ถึงจะรันคำสั่งได้ และใช้ดึงอัปเดต repo |
| **VS Code** | `winget install Microsoft.VisualStudioCode` | โปรแกรมหลักที่ใช้คุยกับ Claude |
| **Node.js LTS** | `winget install OpenJS.NodeJS.LTS` | ให้ใช้คำสั่ง `npm` / `npx` ได้ (Remotion, Remotion Skill และ claude-mem ต้องใช้) |
| **Python 3.11** | `winget install Python.Python.3.11` | ใช้รันสคริปต์ตัด Shorts และเครื่องมือดาวน์โหลด |
| **FFmpeg** | `winget install Gyan.FFmpeg` | ตัดหรือแปลงไฟล์วิดีโอ และดึงเฟรมภาพจากคลิปให้ Claude "ดู" |
| **CapCut** | `winget install ByteDance.CapCut` | ใช้ตัดต่อ และทำ Auto Caption ภาษาไทย |
| **Bun** | `winget install Oven-sh.Bun` | ตัวรันที่ plugin claude-mem ต้องใช้ |
| **GitHub CLI** | `winget install GitHub.cli` | ใช้ล็อกอิน GitHub เพื่อดึงอัปเดต repo ส่วนตัวนี้ |

### 2. Claude

| ตัว | ติดตั้งด้วย | มีไว้ทำอะไร |
|---|---|---|
| **Claude Code (CLI)** | `irm https://claude.ai/install.ps1 \| iex` | ตัว Claude ที่ใช้รันคำสั่งและจัดการ plugin |
| **Claude Code (ส่วนเสริม VS Code)** | `code --install-extension anthropic.claude-code` | แผง Claude ใน VS Code |

### 3. เครื่องมือดึงคลิปและข้อมูลจากเน็ต

Claude ดูวิดีโอตรง ๆ ไม่ได้ ต้องให้เครื่องมือพวกนี้โหลดคลิปมาก่อน จากนั้น Claude จะอ่านซับและดูภาพนิ่งที่ดึงออกมาแทน

| ตัว | ติดตั้งด้วย | มีไว้ทำอะไร |
|---|---|---|
| **yt-dlp** | `pip install yt-dlp` (อยู่ใน `%USERPROFILE%\.tz-tools`) | โหลดวิดีโอและซับจาก YouTube, X, Facebook, IG, TikTok — IG และ FB มักต้องใช้ cookie จากเบราว์เซอร์ที่ล็อกอินไว้ |
| **agent-reach** (CLI + Skill) | `pip install agent-reach` แล้ว `agent-reach install --env local` | ค้นหาข้อมูลและอ่านเนื้อหาจาก YouTube, GitHub, เว็บทั่วไป, RSS (เช็คได้ด้วย `agent-reach doctor`) |
| **x-scraper-toolkit** (`fxtweet.py`) | `git clone https://github.com/alienrelics/x-scraper-toolkit` ไปที่ `%USERPROFILE%\tools\` | อ่านข้อความ ยอดไลก์ และสื่อในทวีต (เพราะ x.com บล็อกการดึงแบบปกติ) |
| **notebooklm-py** | `pip install notebooklm-py playwright rookiepy` + `playwright install chromium` | สั่ง Google NotebookLM ถอด transcript และสรุปคลิป YouTube |

### 4. ระบบตัด Shorts (`shorts-pipeline\`)

| ตัว | ติดตั้งด้วย | มีไว้ทำอะไร |
|---|---|---|
| **venv ใหม่** | `py -3.11 -m venv shorts-pipeline\venv` + `pip install -r requirements.txt` | ไลบรารีของสคริปต์ (faster-whisper, pythainlp, opencv ฯลฯ) |
| ไลบรารี NVIDIA | `requirements-nvidia.txt` (ติดตั้งเฉพาะเครื่องที่มีการ์ด NVIDIA) | ให้ Whisper รันบนการ์ดจอ |
| **โมเดล Whisper ภาษาไทย** | โหลดจาก HuggingFace `Vinxscribe/biodatlab-whisper-th-large-v3-faster` (2.9 GB) ไปที่ `shorts-pipeline\models\` | ถอดเสียงไทยเป็นซับ ใช้เป็นตัวสำรองเวลาใช้ Auto Caption ของ CapCut ไม่ได้ |
| **draft ต้นแบบ CapCut** | ก๊อป `capcut-donor\drafts\*` ไปไว้ในโฟลเดอร์ draft ของ CapCut | เป็นที่มาของพรีเซ็ตสี แต่งหน้า ขอบซับ และการล็อกภาพกับเสียง ที่สคริปต์ดึงไปใช้ |
| **effect ของ CapCut** | ก๊อป `capcut-donor\effects\*` ไปไว้ใน cache ของ CapCut | ไฟล์ effect ที่ draft ต้นแบบเรียกใช้ |

### 5. Skill และ Plugin ของ Claude

| ตัว | ติดตั้งด้วย | มีไว้ทำอะไร |
|---|---|---|
| **shorts-edit** (Skill) | ก๊อปจาก `skills\` | พิมพ์ `/shorts-edit` แล้ว Claude จะรันสคริปต์ตัดคลิปตามลำดับที่ถูกต้อง |
| **notebooklm** (Skill) | ก๊อปจาก `skills\` | สอน Claude ใช้ NotebookLM |
| **diagnosing-bugs** (Skill) | ก๊อปจาก `skills\` | ใช้ตอนสคริปต์พัง Claude จะไล่หาสาเหตุทีละขั้น ไม่เดาแก้ |
| **Remotion Agent Skill** | `npx skills add remotion-dev/skills -g -a claude-code` | สอน Claude เขียนโค้ด Remotion ให้ถูกวิธี |
| **superpowers** (Plugin) | `claude plugin install superpowers@claude-plugins-official` | ชุดขั้นตอนสำหรับวางแผน ดีบั๊ก และตรวจงานก่อนบอกว่าเสร็จ |
| **caveman** (Plugin) | `claude plugin install caveman@caveman` | ทำให้ Claude ตอบสั้นและประหยัด token (ถ้าอยากให้ตอบปกติ พิมพ์ `normal mode`) |
| **claude-mem** (Plugin) | `claude plugin install claude-mem@thedotmack` | ให้ Claude จำเรื่องข้ามแชตได้ |

### 6. Remotion (`remotion\`)

| ตัว | ติดตั้งด้วย | มีไว้ทำอะไร |
|---|---|---|
| **Remotion 4.0.532** | `npm install` ในโฟลเดอร์ `remotion\` | สร้างกราฟิกและวิดีโอด้วยโค้ด เช่น ไตเติล ซับเด้ง intro — เป็นตัวเสริม ไม่ได้แทน CapCut |
| **Chrome Headless Shell** | `npx remotion browser ensure` | เบราว์เซอร์ที่ Remotion ใช้ render |

ใช้งาน: `cd remotion` แล้ว `npm run studio` เพื่อดูตัวอย่าง หรือ `npm run render` เพื่อ export เป็น `out\short.mp4`
⚠️ Remotion ฟรีสำหรับบุคคลทั่วไปและทีมไม่เกิน 3 คน ถ้าใหญ่กว่านั้นต้องซื้อไลเซนส์ (ดู remotion.dev/license)

---

## ใช้งานประจำวัน

1. เปิด VS Code → **File → Open Folder** → เลือกโฟลเดอร์ repo นี้ (Claude จะอ่าน `CLAUDE.md` เอง)
2. ใน CapCut: สร้าง draft ใหม่ → ใส่คลิป → **Captions → Auto captions → Thai** → ตัดช่วงเงียบหรือเทคซ้ำเอง → **ปิด CapCut**
3. ใน Claude พิมพ์ `/shorts-edit` แล้วบอกชื่อ draft
4. รอจน Claude บอกว่าเสร็จ แล้วค่อยเปิด CapCut ดูงาน

🟥 **ห้ามเปิด CapCut ระหว่างที่สคริปต์รันอยู่** เพราะ CapCut จะเขียนทับและงานจะหายไปเฉย ๆ

## ดึงอัปเดต

ถ้าเครื่องติดตั้งโดย `git clone`: ให้พิมพ์ `git pull` แล้วรัน `setup.ps1` ซ้ำ
ถ้าติดตั้งโดยโหลด ZIP: ให้โหลด ZIP ใหม่ทับโฟลเดอร์เดิม (ระวังอย่าลบ `shorts-pipeline\venv` กับ `models`)

## ไม่ได้รวมไว้ใน repo นี้

- ไฟล์งานคลิปเก่า ฟุตเทจ และเสียง
- รหัสผ่าน cookie และไฟล์ล็อกอินทุกชนิด — แต่ละคนต้องล็อกอินเอง
