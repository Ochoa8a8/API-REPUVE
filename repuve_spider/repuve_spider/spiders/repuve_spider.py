import scrapy
from PIL import Image
import pytesseract

# Path to tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'


class RepuveSpider(scrapy.Spider):
    name = "plate"
    start_urls = ["http://www2.repuve.gob.mx:8080/ciudadania/servletconsulta"]
    plate = {}

    def parse(self, response):
        # In case you retry, not rewrite plate
        try:
            if not self.plate:
                self.plate = response.meta['plate']
        except:
            pass
        return scrapy.Request(url="http://www2.repuve.gob.mx:8080/ciudadania/jcaptcha", callback=self.parse_captcha,
                              meta={'previous_response': response}, dont_filter=True)

    def parse_captcha(self, response):
        # Save captcha image
        with open('captcha.png', 'wb') as f:
            f.write(response.body)
        # Solve captcha
        pil = Image.open("captcha.png")
        captcha = read_captcha(pil)
        # Check if plate was introduced, else stop spider and return error
        if not self.plate:
            data = {
                'error': 'No se introdujo placa'
            }
            return data
        # Send form request with plate and solved captcha
        return scrapy.FormRequest.from_response(
            response=response.meta['previous_response'],
            formdata={'captcha': captcha,
                      'folio': None,
                      'nrpv': None,
                      'pageSource': 'index.jsp',
                      'placa': self.plate,
                      'vin': None},
            callback=self.after_captcha,
            dont_filter=True)

    def after_captcha(self, response):
        # Check response for incorrect captcha response
        solved = response.xpath('//*[@id="txtError"]/text()').get()
        fail = 'El texto de la imagen y el que captura deben ser iguales'
        try:
            if fail in solved:
                print('FAILED...RETRYING')
                return scrapy.Request(url="http://www2.repuve.gob.mx:8080/ciudadania/servletconsulta",
                                      callback=self.parse, dont_filter=True)
        except:
            # Else print success
            print('CAPTCHA passed!')
        # Return error: incorrect/non existing plate
        incorrect_plate = response.xpath('//p/text()').get()
        message = 'PLACA no encontrada'
        try:
            if message in incorrect_plate:
                data = {
                    'error': 'No se encontro la placa'
                }
                return data
        except:
            pass
        # Return data yielded with plate
        data = {
            'brand': response.xpath('//table/tr[1]/td[2]//text()').get(),
            'model': response.xpath('//table/tr[2]/td[2]//text()').get(),
            'yearModel': response.xpath('//table/tr[3]/td[2]//text()').get(),
            'class_': response.xpath('//table/tr[4]/td[2]//text()').get(),
            'type_': response.xpath('//table/tr[5]/td[2]//text()').get(),
            'niv': response.xpath('//table/tr[6]/td[2]//text()').get(),
            'nci': response.xpath('//table/tr[7]/td[2]//text()').get(),
            'plate': response.xpath('//table/tr[8]/td[2]//text()').get(),
            'doors': response.xpath('//table/tr[9]/td[2]//text()').get(),
            'originCity': response.xpath('//table/tr[10]/td[2]//text()').get(),
            'version': response.xpath('//table/tr[11]/td[2]//text()').get(),
            'ccl': response.xpath('//table/tr[12]/td[2]//text()').get(),
            'cylinders': response.xpath('//table/tr[13]/td[2]//text()').get(),
            'axles': response.xpath('//table/tr[14]/td[2]//text()').get(),
            'assemblyPlant': response.xpath('//table/tr[15]/td[2]//text()').get(),
            'extra': response.xpath('//table/tr[16]/td[2]//text()').get(),
            'enrolledInstitution': response.xpath('//table/tr[17]/td[2]//text()').get(),
            'enrolledDate': response.xpath('//table/tr[18]/td[2]//text()').get(),
            'enrolledHour': response.xpath('//table/tr[19]/td[2]//text()').get(),
            'registrationEntity': response.xpath('//table/tr[20]/td[2]//text()').get(),
            'registrationDate': response.xpath('//table/tr[21]/td[2]//text()').get(),
            'lastUpdate': response.xpath('//table/tr[22]/td[2]//text()').get(),
            'PGJ': response.xpath('//*[@id="tab-avisoRobo"]/div/text()').get(),
            'OCRA': response.xpath('//*[@id="tab-ocra"]/div[1]/text()').get(),
        }
        return data


def read_captcha(pil):
    thresh = 230
    fn = lambda x: 0 if x > thresh else 255
    bw = pil.convert('L').point(fn, mode='1')
    bw.save('captcha_thresholded.png')
    captcha = pytesseract.image_to_string(bw)
    captcha.replace(" ", "")
    print('Captcha solved:', captcha)
    return captcha
