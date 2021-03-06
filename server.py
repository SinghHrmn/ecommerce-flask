from flask import Flask, render_template, request, url_for
from flask import redirect, flash, jsonify, make_response
from model import ProductModel, CatalogModel, UserModel
from model import GlobalCatalogModel, Workers
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker
from database import Catalog, Product, Base
from functools import wraps

# Login Imports
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
import requests
import os
__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))


app = Flask(__name__)


# Login Flow
def checkLogin():
    if 'username' not in login_session:
        return False
    else:
        return True


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' in login_session:
            return f(*args, **kwargs)
        else:
            flash("Login required", "error")
            return redirect('/login')
    return decorated_function


@app.route('/login')
def showLogin():
    state = ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(32))
    login_session['state'] = state
    links = Workers().getNavLinks()
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', navlinks=links, STATE=state)


CLIENT_ID = json.loads(
    open(os.path.join(__location__, 'client_secrets.json'),
         'r').read())['web']['client_id']


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    user_id = UserModel().getUserID(login_session['email'])
    if not user_id:
        user_id = UserModel().createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ''' " style =
                    "width: 300px;
                    height: 300px;
                    border-radius: 150px;
                    -webkit-border-radius: 150px;
                    -moz-border-radius: 150px;"> '''
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

    # DISCONNECT - Revoke a current user's token and reset their login_session


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps(
            'Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    revoke_url = 'https://accounts.google.com/o/oauth2/revoke?token='
    url = revoke_url + login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps(
            'Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect("/")
    else:
        response = make_response(json.dumps(
            'Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# Home route
@app.route('/')
def index():
    products = ProductModel().products(1)
    loggedin = checkLogin()
    links = Workers().getNavLinks()
    slider = Workers().getSlider()
    return render_template('index.html',
                           navlinks=links, products=products,
                           loggedin=loggedin, slider=slider)


# Category page
@app.route('/catalog/<int:catalog_id>/products')
def categoryCatalog(catalog_id):
    products = ProductModel().products(catalog_id)
    catalog = CatalogModel().catalog(catalog_id)
    loggedin = checkLogin()
    links = Workers().getNavLinks()
    return render_template('category.html',
                           navlinks=links, catalog=catalog,
                           products=products, loggedin=loggedin)


# Product page
@app.route('/catalog/<int:catalog_id>/product/<int:id>')
def productPage(catalog_id, id):
    product = ProductModel().product(id)
    catalog = CatalogModel().catalog(catalog_id)
    loggedin = checkLogin()
    links = Workers().getNavLinks()
    return render_template('product.html',
                           navlinks=links, product=product,
                           catalog=catalog, loggedin=loggedin)


# Products JSON
@app.route('/catalog/<int:catalog_id>/products/JSON')
def categoryCatalogJSON(catalog_id):
    products = ProductModel().products(catalog_id)
    return jsonify(products=[i.serialize for i in products])


# Product JSON
@app.route('/product/<int:id>/JSON')
def productJSON(id):
    product = ProductModel().product(id)
    return jsonify(product=[product.serialize])


# Catalogs JSON
@app.route('/catalogs/JSON')
def catalogsJSON():
    return jsonify(Workers().catalogsJSON())


# Admin home route
@app.route('/admin')
@login_required
def adminHome():
    catalogs = Workers().getNavLinks()
    print(login_session)
    return render_template('admin/index.html', catalogs=catalogs)


# Admin category edit route
@app.route('/admin/catalog/<int:catalog_id>', methods=['GET', 'POST'])
@login_required
def adminCatalog(catalog_id):
    catalog = CatalogModel().catalog(catalog_id)
    if request.method == 'POST':
        if Workers().checkAuth(catalog.user_id, login_session):
            CatalogModel().updateCatalog(request.form)
            catalog = CatalogModel().catalog(catalog_id)
            flash("Catalog edited sucessfully")
            return render_template('admin/catalog.html', catalog=catalog)
        else:
            flash("Catalog can only be edited by creator", "error")
            return render_template('admin/catalog.html', catalog=catalog)
    else:
        return render_template('admin/catalog.html', catalog=catalog)


# Admin category delete route
@app.route('/admin/catalog/<int:catalog_id>/delete', methods=['GET', 'POST'])
@login_required
def deleteCatalog(catalog_id):
    catalog = CatalogModel().catalog(catalog_id)
    if request.method == 'POST':
        if Workers().checkAuth(catalog.user_id, login_session):
            CatalogModel().deleteCatalog(catalog_id)
            flash("Catalog deleted sucessfully")
            return redirect("/admin")
        else:
            flash("Catalog can only be deleted by creator", "error")
            return render_template('admin/catalog.html', catalog=catalog)

    else:
        return render_template('admin/deleteCatalog.html', catalog=catalog)


# Admin new category route
@app.route('/admin/<global_id>/catalog/new', methods=['GET', 'POST'])
@login_required
def newCatalog(global_id):
    if request.method == 'POST':
        CatalogModel().createCatalog(request.form, login_session['user_id'])
        flash("Catalog created sucessfully")
        return redirect("/admin")
    else:
        global_catalog = GlobalCatalogModel().global_catalog(global_id)
        return render_template('admin/newCatalog.html',
                               global_catalog=global_catalog)


# Admin category products view
@app.route('/admin/catalog/<int:catalog_id>/products')
@login_required
def adminProducts(catalog_id):
    products = ProductModel().products(catalog_id)
    catalog = CatalogModel().catalog(catalog_id)
    return render_template('admin/products.html',
                           catalog=catalog, products=products)


# Admin products edit route
@app.route('/admin/catalog/<int:catalog_id>/product/<int:product_id>',
           methods=['GET', 'POST'])
@login_required
def productView(catalog_id, product_id):
    catalog = CatalogModel().catalog(catalog_id)
    product = ProductModel().product(product_id)
    if request.method == 'POST':
        if Workers().checkAuth(product.user_id, login_session):
            ProductModel().updateProduct(request.form)
            flash("Product sucessfully edited")
            return redirect(url_for('adminProducts', catalog_id=catalog_id))
        else:
            flash("Product can only be edited by creator", "error")
            return redirect(url_for('adminProducts', catalog_id=catalog_id))
    else:
        product = ProductModel().product(product_id)
        catalog = CatalogModel().catalog(catalog_id)
        return render_template('admin/product.html',
                               product=product, catalog=catalog)


# Admin product delete route
@app.route('/admin/catalog/<int:catalog_id>/product/<int:product_id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteProduct(catalog_id, product_id):
    catalog = CatalogModel().catalog(catalog_id)
    product = ProductModel().product(product_id)
    if request.method == 'POST':
        if Workers().checkAuth(product.user_id, login_session):
            ProductModel().deleteProduct(product_id)
            flash("Product sucessfully deleted")
            return redirect(url_for('adminProducts', catalog_id=catalog_id))
        else:
            flash("Product can only be deleted by creator", "error")
            return redirect(url_for('adminProducts', catalog_id=catalog_id))
    else:
        product = ProductModel().product(product_id)
        catalog = CatalogModel().catalog(catalog_id)
        return render_template('admin/deleteProduct.html',
                               catalog=catalog, product=product)


# Admin new product route
@app.route('/admin/catalog/<int:catalog_id>/product/new',
           methods=['GET', 'POST'])
@login_required
def newProduct(catalog_id):
    if request.method == 'POST':
        ProductModel().createProduct(request.form, login_session['user_id'])
        flash("Product sucessfully created")
        print("Product created by user: %s" % login_session['user_id'])
        return redirect(url_for('adminProducts', catalog_id=catalog_id))
    else:
        catalog = CatalogModel().catalog(catalog_id)
        return render_template('admin/newProduct.html', catalog=catalog)


# Admin user crud route
@app.route('/admin/user/<int:user_id>',
           methods=['GET', 'PUT', 'POST', 'DELETE'])
@login_required
def userView(user_id):
    user = UserModel().user(user_id)
    if request.method == 'PUT':
        UserModel().updateUser(request.form)
    elif request.method == 'POST':
        UserModel().createUser(request.form)
    elif request.method == 'DELETE':
        UserModel().deleteUser(request.form['id'])
    else:
        return render_template('admin/user.html', user=user)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
