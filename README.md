# CURL Commander (Burp Suite Extension)

> **Easily import curl commands directly into Burp Suite's Repeater.**

CURL Commander is a Burp Suite extension built using **Python (Jython)**. It quickly transforms clipboard-copied `curl` commands into HTTP requests within Burp Suite's Repeater, eliminating manual request reconstruction.

---

## 🚀 Features

- **Instant Import**: Parses `curl` commands directly from your clipboard.
- **Easy Integration**: Adds a right-click context menu item for seamless workflow.
- **Robust Parsing**:
  - Handles multiple headers (`-H`, `--header`)
  - Supports different HTTP methods (`GET`, `POST`, `PUT`, `DELETE`, etc.)
  - Supports request bodies (JSON, form-data, multipart, URL-encoded)

---

## 📦 Installation

### Prerequisites
- [Burp Suite](https://portswigger.net/burp)
- [Jython Standalone](https://www.jython.org/download)

### Setup Steps
1. **Download** `curl-commander.py` from this repository.
2. Open Burp Suite → Navigate to **Extender** → **Extensions** tab.
3. Click **Add**, select **Python** as extension type.
4. Select your downloaded `curl-commander.py` and click **Next**.

Your extension is now loaded and ready to use!

---

## 🚦 Usage

1. Copy a valid `curl` command to your clipboard:
    ```bash
    curl -X POST https://example.com/api \
         -H "Authorization: Bearer TOKEN" \
         -H "Content-Type: application/json" \
         -d '{"key":"value"}'
    ```

2. In Burp Suite, right-click anywhere and select:
    ```
    Curl-Commander > Send CURL to Repeater
    ```

3. The request opens automatically in a new Repeater tab.

---


## 📄 License

MIT © amitdubey

---

## 🤝 Contributions

Issues and pull requests are welcome! Feel free to contribute enhancements or bug fixes.
