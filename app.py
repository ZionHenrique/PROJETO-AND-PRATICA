from flask import Flask, render_template, request, jsonify
import os
import json
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

app = Flask(__name__)

# ============================
# Carrega dados e treina modelo
# ============================

DATA_PATH = os.path.join(os.path.dirname(__file__), 'Students_gamification_grades.csv')

# Definição de colunas conforme o CSV fornecido
NUMERIC_FEATURES = [
    'Practice_Exam',
    'User',
    'Avg_Grade_Q1','Avg_Grade_Q2','Avg_Grade_Q3','Avg_Grade_Q4','Avg_Grade_Q5','Avg_Grade_Q6',
    'No_access_Q1','No_access_Q2','No_access_Q3','No_access_Q4','No_access_Q5','No_access_Q6'
]
TARGET_COLUMN = 'Final_Exam'

model_pipeline = None

def load_and_train_model():
    global model_pipeline
    if not os.path.exists(DATA_PATH):
        return

    df = pd.read_csv(DATA_PATH)

    # Garante presença das colunas esperadas
    missing = [c for c in NUMERIC_FEATURES + [TARGET_COLUMN] if c not in df.columns]
    if missing:
        return

    # Feature engineering simples inspirado no painel: médias e somas auxiliares
    avg_cols = [c for c in df.columns if c.lower().startswith('avg_grade_q')]
    no_cols = [c for c in df.columns if c.lower().startswith('no_access_q')]
    df['avg_all_q'] = df[avg_cols].mean(axis=1)
    df['total_no_access'] = df[no_cols].sum(axis=1)

    features = NUMERIC_FEATURES + ['avg_all_q', 'total_no_access']
    X = df[features]
    y = df[TARGET_COLUMN]

    preprocessor = ColumnTransformer(
        transformers=[('num', StandardScaler(), features)],
        remainder='drop'
    )

    regressor = RandomForestRegressor(n_estimators=300, random_state=42)

    model_pipeline = Pipeline(steps=[
        ('prep', preprocessor),
        ('model', regressor)
    ])

    # train/test split para evitar sobreajuste no ajuste dos parâmetros internos
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model_pipeline.fit(X_train, y_train)


# Treina o modelo ao iniciar o app
load_and_train_model()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/previsor')
def previsor():
    return render_template('previsor.html')


@app.route('/api/predict', methods=['POST'])
def api_predict():
    if model_pipeline is None:
        return jsonify({'error': 'Modelo indisponível'}), 503

    try:
        payload = request.get_json(force=True, silent=True) or {}

        # Aceita tanto os campos originais quanto as features agregadas (se fornecidas)
        def num(v):
            try:
                return float(v)
            except Exception:
                return np.nan

        # Extrai valores com defaults seguros
        values = {
            'Practice_Exam': num(payload.get('Practice_Exam', 0)),
            'User': num(payload.get('User', 0)),
            'Avg_Grade_Q1': num(payload.get('Avg_Grade_Q1', 0)),
            'Avg_Grade_Q2': num(payload.get('Avg_Grade_Q2', 0)),
            'Avg_Grade_Q3': num(payload.get('Avg_Grade_Q3', 0)),
            'Avg_Grade_Q4': num(payload.get('Avg_Grade_Q4', 0)),
            'Avg_Grade_Q5': num(payload.get('Avg_Grade_Q5', 0)),
            'Avg_Grade_Q6': num(payload.get('Avg_Grade_Q6', 0)),
            'No_access_Q1': num(payload.get('No_access_Q1', 0)),
            'No_access_Q2': num(payload.get('No_access_Q2', 0)),
            'No_access_Q3': num(payload.get('No_access_Q3', 0)),
            'No_access_Q4': num(payload.get('No_access_Q4', 0)),
            'No_access_Q5': num(payload.get('No_access_Q5', 0)),
            'No_access_Q6': num(payload.get('No_access_Q6', 0)),
        }

        # Se o cliente já enviar agregados, usamos; caso contrário calculamos com base nas médias
        avg_all_q = payload.get('avg_all_q')
        total_no_access = payload.get('total_no_access')
        if avg_all_q is None:
            avg_from_inputs = np.nanmean([
                values['Avg_Grade_Q1'], values['Avg_Grade_Q2'], values['Avg_Grade_Q3'],
                values['Avg_Grade_Q4'], values['Avg_Grade_Q5'], values['Avg_Grade_Q6']
            ])
            values['avg_all_q'] = float(0 if np.isnan(avg_from_inputs) else avg_from_inputs)
        else:
            values['avg_all_q'] = num(avg_all_q)

        if total_no_access is None:
            sum_from_inputs = np.nansum([
                values['No_access_Q1'], values['No_access_Q2'], values['No_access_Q3'],
                values['No_access_Q4'], values['No_access_Q5'], values['No_access_Q6']
            ])
            values['total_no_access'] = float(0 if np.isnan(sum_from_inputs) else sum_from_inputs)
        else:
            values['total_no_access'] = num(total_no_access)

        X = pd.DataFrame([values])
        y_pred = model_pipeline.predict(X)[0]
        # Garante faixa 0-10
        y_pred_clamped = float(max(0, min(10, y_pred)))

        return jsonify({
            'prediction': y_pred_clamped,
            'inputs': values
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
