from app import app

if __name__ == "__main__":
    # Для разработки на Windows
    app.run(debug=True, host='0.0.0.0', port=5000)