from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/entrada")
def entrada():
    return render_template("entrada.html")


@app.route("/salida")
def salida():
    return render_template("salida.html")


if __name__ == "__main__":
    app.run(debug=True)
