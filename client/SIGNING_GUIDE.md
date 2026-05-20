# EXE Code Signing Guide

## Problem
Unsigned EXE files trigger Windows SmartScreen warning: "This app isn't commonly downloaded..."

## Solutions

### 1. Purchase Code Signing Certificate (Recommended)
**Cost**: $200-700/year
**Benefits**:
- Permanent solution
- Builds user trust
- Professional appearance

**Providers**:
- DigiCert
- Sectigo (Cost-effective)
- GlobalSign
- Alibaba Cloud / Tencent Cloud (Easy purchase in China)

**Steps**:
```bash
1. Buy code signing certificate from Alibaba/Tencent Cloud
2. Verify company identity
3. Download certificate (PFX format)
4. Use sign.bat to sign
```

### 2. EV Code Signing Certificate (Best but Expensive)
**Cost**: $1000+/year
**Benefits**:
- Immediate SmartScreen trust
- No reputation building needed

### 3. Microsoft SmartScreen Whitelist
**Cost**: Free
**Steps**:
1. Submit EXE to Microsoft
2. Wait for analysis (weeks)
3. Get信誉 after approved

### 4. Build Reputation Automatically
**Cost**: Free
**Info**:
- EXE gets downloaded and run multiple times
- SmartScreen learns automatically
- Takes weeks to months

**Drawback**: First run still shows warning

## Quick Start

### Step 1: Modify sign-config.bat
Copy `sign-config-example.bat` to `sign-config.bat`, enter password

### Step 2: Run signing
```bash
cd d:\fh\client
build.bat
```

### Step 3: Test
First run may still be blocked, will work after repeated runs

## Common Issues

### Q: Need to restart PC?
A: No, signing is file-level only

### Q: What if certificate expires?
A: Re-sign, or update certificate

### Q: Can self-signed certificate work?
A: Yes, but SmartScreen won't trust it, still blocked

### Q: Still blocked after signing?
A: Normal, needs time for SmartScreen to learn. Run multiple times or apply for whitelist

## Tools

### Windows SDK (includes signtool)
https://developer.microsoft.com/windows/downloads/windows-sdk/

### OpenSSL for Windows
https://slproweb.com/products/Win32OpenSSL.html

### osslsigncode (Open Source)
https://github.com/mtroelper/osslsigncode/releases
