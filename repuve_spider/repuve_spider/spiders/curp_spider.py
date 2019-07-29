import scrapy
from PIL import Image
import pytesseract
import cv2
import numpy as np
import PIL.ImageOps
from operator import itemgetter
import re

# Path to tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'


class RepuveSpider(scrapy.Spider):
    name = "curp"
    start_urls = ["https://consultas.curp.gob.mx/CurpSP/gobmx/inicio.jsp"]
    curp = []

    def parse(self, response):
        # In case you retry, not rewrite curp
        try:
            if not self.curp:
                self.curp = response.meta['curp']
        except:
            pass
        return scrapy.Request(url="https://consultas.curp.gob.mx/CurpSP/captchaCurp", callback=self.parse_captcha,
                              meta={'previous_response': response}, dont_filter=True)

    def parse_captcha(self, response):
        # Save captcha image
        with open('captcha.png', 'wb') as f:
            f.write(response.body)
        # Solve captcha
        pil = Image.open("captcha.png")
        captcha = read_captcha(pil)
        # Captcha is always 5 chars long, else is incorrect
        if len(captcha) != 5:
            print('FAILED...RETRYING')
            return scrapy.Request(url="https://consultas.curp.gob.mx/CurpSP/gobmx/inicio.jsp",
                                  callback=self.parse, dont_filter=True)
        # Check if curp was introduced, else stop spider and return error
        if not self.curp:
            data = {
                'error': 'No se introdujo el CURP'
            }
            return data
        # Send form request with curp and solved captcha
        return scrapy.FormRequest.from_response(
            response=response.meta['previous_response'],
            formdata={'codigo': captcha,
                      'strCurp': self.curp},
            callback=self.after_captcha,
            dont_filter=True,
            dont_click=True)

    def after_captcha(self, response):
        # Check response for incorrect captcha response
        solved = response.xpath('//h3//text()').get()
        fail = 'Error en datos de entrada'
        try:
            if fail in solved:
                print('FAILED...RETRYING')
                return scrapy.Request(url="https://consultas.curp.gob.mx/CurpSP/gobmx/inicio.jsp",
                                      callback=self.parse, dont_filter=True)
        except:
            # Else print success
            print('CAPTCHA passed!')
        # Return error: incorrect/non existing curp
        incorrect_plate = response.xpath('//h4//text()').getall()
        message = 'no se encuentra en la Base de Datos Nacional de la CURP'
        try:
            if message in incorrect_plate[2]:
                data = {
                    'error': 'No se encontro el CURP'
                }
                return data
        except:
            pass
        # Return data yielded with curp
        dict = response.xpath('//table//strong/text()').getall()
        data = {
            'name': dict[0],
            'paternal_surname': dict[1],
            'maternal_surname': dict[2],
            'sex': dict[3],
            'birth_date': dict[4],
            'citizenship': dict[5],
            'birth_entity': dict[6],
        }
        return data


def read_captcha(pil):
    # Turn into black and white
    thresh = 220
    fn = lambda x: 0 if x > thresh else 255
    bw = pil.convert('L').point(fn, mode='1')
    bw.save('captcha_thresholded.png')
    # Clean lines
    img = cv2.imread('captcha_thresholded.png', 0)
    kernel = np.ones((3, 3), np.uint8)
    erosion = cv2.erode(img, kernel, iterations=1)
    erosion = cv2.copyMakeBorder(erosion, 5, 5, 5, 5, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    cv2.imwrite('captcha_cleaned.png', erosion)
    # Invert colors
    captcha_img = Image.open("captcha_cleaned.png")
    inverted_image = PIL.ImageOps.invert(captcha_img)
    inverted_image.save('inverted_captcha.png')
    # Load image and prepare for processing
    test = cv2.pyrDown(cv2.imread('inverted_captcha.png'))
    ret, threshed_img = cv2.threshold(cv2.cvtColor(test, cv2.COLOR_BGR2GRAY),
                                      127, 255, cv2.THRESH_BINARY)
    # Get contours
    contours, hier = cv2.findContours(threshed_img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    # Create new image to paste letters
    blank_image = Image.new('RGBA', (400, 80), 'white')
    cropping_img = Image.open('inverted_captcha.png')
    total_width = 0
    coordinates = []
    # Save bounding boxes of letters
    for c in contours:
        # Get the bounding rect
        x, y, w, h = cv2.boundingRect(c)
        # Draw a green rectangle to visualize the bounding rect
        cv2.rectangle(test, (x, y), (x + w, y + h), (0, 255, 0), 1)
        if 100 > w and h >= 20:
            coordinates.append([x, y, w, h])
    # Sort the letters to keep the right order
    coordinates.sort(key=itemgetter(0))
    print(coordinates)
    # Paste letters in order
    for idx, cords in enumerate(coordinates):
        x, y, w, h = coordinates[idx][0], coordinates[idx][1], coordinates[idx][2], coordinates[idx][3],
        crop = cropping_img.crop((x*2, y*2, (x+w)*2, (y+h)*2))
        blank_image.paste(crop, (0+total_width, 0))
        total_width += w*2+20
    # Save image
    blank_image.convert('RGB').save('final.jpg')
    cv2.imwrite('captcha_boxes.png', test)
    # Solve captcha
    final = Image.open('final.jpg')
    captcha = pytesseract.image_to_string(final, config='--psm 6')
    # Clean captcha and print
    captcha = re.sub('[^A-Za-z0-9]+', '', captcha)
    print('Captcha solved:', captcha)

    return captcha
