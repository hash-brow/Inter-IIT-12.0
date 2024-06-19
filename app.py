# from distutils.log import debug
from fileinput import filename
import pandas as pd
from flask import *
import os
from werkzeug.utils import secure_filename
import csv
from Cleaner1 import temp_files
from Ash1 import main1
from Converter import main2
import zipfile
UPLOAD_FOLDER = os.path.join('staticFiles', 'uploads')

current_step = 1

List1 = ['FirstClass', 'BusinessClass', 'PremiumEconomyClass', 'EconomyClass', 'DEAF', 'WCHR', 'BLND', 'NRSA',
         'NRPS', 'Platinum', 'Gold', 'Silver', 'S65', 'ADT', 'CHD', 'INF', 'INS', 'UNN', 'GN', 'PAX']

display_Names = ['First Class', 'Business Class', 'Premium Economy Class', 'Economy Class', 'Deaf', 'Wheel Chair',' Blind', 'NRSA', 'NRPS', 'Platinum Customer', 'Gold Customer', 'Silver Customer', 'Aged Customer', 'Adult', 'Child', 'Infant', 'Minor with Accompany', 'Unaccompanied Minor', 'Group Ticket', 'Passenger Count']

default_values = [1000, 800, 600, 500, 200, 200, 200, 750,
                  1000, 2000, 1750, 1500, 500, 0, 500, 750, 1000, 1000, 500, 50]

default_checked = [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0]

ALLOWED_EXTENSIONS = {'csv'}

app = Flask(__name__, static_folder='staticFiles')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = 'This is your secret key to utilize session in Flask'

def generate_zip(filepath):
    zip_path = os.path.join()

# @app.route('/zero')
# def home():



#     render_template('index_new.html', rule_list=List1, default_values=default_values, default_checked=default_checked, current_step=1, file='PNR Passenger Data')

# @app.route('/one')
# def uploadCSV():


@app.route('/', methods=['GET', 'POST'])
def uploadFile():
    global current_step
    global flights_cancelled
    global Max_layover_time, Min_layover_time, Max_departure_delay, downline
    global default_constant, multi_leg_constant, infty_constant, class_constant
    global DwaveToken
    if request.method == 'POST':
        if current_step == 1:
            f1 = request.files.get('f1')
            f2 = request.files.get('f2')
            f3 = request.files.get('f3')
            f4 = request.files.get('f4')
            if f1 and f2 and f3 and f4:
                current_step += 1
                f1.save(os.path.join(app.config['UPLOAD_FOLDER'], 'PNRP.csv'))
                f2.save(os.path.join(app.config['UPLOAD_FOLDER'], 'PNRB.csv'))
                f3.save(os.path.join(app.config['UPLOAD_FOLDER'], 'SCH.csv'))
                f4.save(os.path.join(app.config['UPLOAD_FOLDER'], 'INV.csv'))
                return render_template('Flight_Cancelling.html', current_step=current_step)

        elif current_step == 2:
            f5 = request.form['subject']
            if f5:
                current_step += 1
                flights_cancelled = list(dict.fromkeys(f5.split(', ')))
            return render_template('Rule_Engine.html', rule_list=List1, default_values=default_values, default_checked=default_checked, current_step=current_step, display_Names=display_Names)


        elif current_step == 3:
            current_step += 1
            rules = [['Condition', 'Score', 'FK']]
            for i in range(1, len(List1)+1):
                rule_weight = int(request.form[f"rule{i}_weight"])
                rule_bool = request.form.get(f"rule{i}_bool") is not None
                rules.append([List1[i-1], rule_weight, rule_bool])

            with open("staticFiles/uploads/RULES.csv", 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rules)

            return render_template('Constants.html', current_step=current_step)
            
        elif current_step == 4:
            current_step += 1
            downline = int(request.form['Downline'])
            Max_departure_delay = int(request.form['Max-Departure-Delay'])*60
            Max_layover_time = int(request.form['Max-Layover-Time'])*60
            Min_layover_time = int(request.form['Min-Layover-Time'])*60
            default_constant = int(request.form['A'])
            class_constant = int(request.form['B'])
            multi_leg_constant = int(request.form['M'])
            infty_constant = int(request.form['I'])

            return render_template('Dwave_Token.html', current_step=current_step)

        elif current_step == 5:
            current_step += 1
            DwaveToken = request.form['subject']

            temp_files()

            main1(flights_cancelled, DwaveToken, downline, Max_departure_delay, Min_layover_time, Max_layover_time, multi_leg_constant, infty_constant, class_constant, default_constant)

            main2(flights_cancelled)

            # return send_from_directory('output',f'{}')
            return render_template('Download.html', current_step = current_step)
        
        elif current_step == 6:
            # file_path = os.path.join9
            zf = zipfile.ZipFile("Output.zip", mode="w")
            zf.write("output/stats.csv")
            for flight in flights_cancelled:
                for q in range(10):
                    zf.write("output/" +str(q)+ "_" + flight + "_exception.csv")
                    zf.write("output/" + str(q) + "_" + flight + "_default.csv")
            # return send_from_directory('output',f'{}')
            zf.close()
            current_step = 1
            return send_from_directory('', 'Output.zip', as_attachment=True)
            return render_template('index_wtver.html')

        # If none of the above conditions match, show the current step
        return render_template('DataSet_Engine.html', current_step=1)

    current_step = 1
    return render_template('DataSet_Engine.html', current_step=1)


if __name__ == '__main__':
    app.run(debug=True)
