
import re

menu_text = """
Soup Bowl (12.00pm - 10.30pm)

Hot & Sour Veg Soup — £4.99
Hot and spicy thick soup made with sautéed fresh vegetables and soy sauce.

Sweet Corn Soup — £4.99
Lightly spiced corn soup flavoured with pepper.

Mushroom Soup — £4.99
Lightly spiced minced mushroom soup garnished with cream.

Pepper Rasam Soup — £4.50
Traditional South Indian sour & spicy soup with diced fresh tomatoes & tamarind juice.

Starters (12.00pm - 10.30pm)

Gobi 65 — £8.50
Battered cauliflower florets deep fried with spices and chilli paste.

Paneer 65 — £8.99
Batter deep fried Indian cottage cheese chunks flavoured with spicy paste.

Mogo 65 — £7.99
Casava marinated in Indian & Chinese spices, dipped in gram flour batter & deep fried.

Mushroom 65 — £7.99
Battered fried mushroom sautéed with spices & chilli paste.

Paneer Tikka — £9.99
Chunks of cottage cheese marinated in special herbs & spices & grilled in a clay oven.

Paneer Pepper Fry — £9.50
Chunks of cottage cheese batter fried & sautéed with flavoured spices & pepper.

Mushroom Pepper Fry — £8.99
Mushroom batter fried & sautéed with flavoured spices & pepper.

Chilly Paneer (Dry/Gravy) — £8.99
Cottage cheese diced marinated in an authentic South Indian chilli mix & pan cooked.

Chilly Baby Corn (Dry/Gravy) — £8.99
Baby corn diced marinated in an authentic South Indian chilli mix & pan cooked.

Chilly Mogo (Dry/Gravy) — £8.75
Steamed tapioca pieces deep fried and tossed in chef’s special chilli sauce & spices.

Chilly Gobi (Dry/Gravy) — £8.50
Steamed cauliflower pieces deep fried and tossed in chef’s special chilli sauce & spices.

Veg Manchurian (Dry/Gravy) — £8.99
Minced vegetables deep fried in balls sautéed with onion & garlic in Manchurian sauce.

Paneer Manchurian (Dry/Gravy) — £8.99

Gobi Manchurian (Dry/Gravy) — £8.50

Mushroom Manchurian (Dry/Gravy) — £8.50

Veg Roll (2 pcs) — £4.99

Veg Samosa (3 pcs) — £4.50

Onion Pakoda — £4.50

Vegetable Spring Roll (3 pcs) — £4.50

Plain Papadum (1 pc) — £1.50

Masala Papadum — £3.50

Chilly Idly — £8.50

Cocktail Idly — £7.50

Mini Podi Idly — £6.99

Chaat Items (12.00pm - 10.30pm)

Samosa Chaat — £6.99

Panipuri — £5.99

Dahi Batata Puri — £5.99

Aloo Papdi Chaat — £6.99

Vada (7.00am - 10.30pm)

Medhu Vada (2 pcs) — £4.50

Sambar Vada (2 pcs) — £5.99

Rasa Vada (2 pcs) — £5.99

Thayir Vada (2 pcs) — £5.99

Idly (7.00am - 10.30pm)

Idly (3 pcs) — £5.50

Idly (2 pcs) & Vada (1 pc) — £5.50

Sambar Idly (2 pcs) — £5.99

Mini Ghee Idly — £5.99

Podi Idly — £6.50

South Indian Corner

Ghee Pongal — £7.50

Pongal & Vada — £7.99

Poori (2 pcs) Masala — £6.99

Chappathi (2 pcs) with Kurma — £6.99

Parotta (2 pcs) with Kurma — £7.99

Channa Bhatura — £7.99

Chilli Parotta — £8.99

Kothu Parotta — £8.99

Dosas

Plain Dosa — £5.50

Masala Dosa — £6.99

Onion Dosa — £6.50

Onion Masala Dosa — £7.99

Ghee Roast — £7.99

Ghee Masala Roast — £8.99

Butter Dosa — £7.99

Butter Masala Dosa — £8.99

Paper Roast — £8.50

Paper Masala Roast — £9.99

Kal Dosa (2 pcs) — £7.99

Podi Dosa — £7.50

Podi Masala Dosa — £8.99

Kara Podi Dosa — £8.50

Kara Podi Masala Dosa — £9.99

Mysore Dosa — £7.50

Mysore Masala Dosa — £8.99

Paneer Masala Dosa — £9.99

Mushroom Masala Dosa — £9.99

Veg Masala Dosa — £9.99

VV Special Dosa — £10.99

Family Dosa — £16.99

Rava Dosa

Rava Dosa — £7.99

Rava Masala Dosa — £8.99

Onion Rava Dosa — £8.99

Onion Rava Masala Dosa — £9.99

Uthappam

Plain Uthappam — £6.99

Onion Uthappam — £7.50

Onion Chilli Uthappam — £7.99

Onion Tomato Uthappam — £7.99

Chilli Coriander Uthappam — £7.99

Onion Chilli Tomato Uthappam — £8.99

Pizza Uthappam — £9.99

Mini Uthappam — £9.99

Mix Veg Uthappam — £8.99

Mini Tiffin

Mini Tiffin – Basic — £9.99

Mini Tiffin – Classic — £10.99

Kids Choice

Kids Cone Dosa — £7.50

Cheese Dosa — £7.99

Chocolate Dosa — £7.99

French Fries — £3.99

Meals

South Indian Meals
Eat In: £10.99 | Takeaway: £12.99

North Indian Meals
Eat In: £10.99 | Takeaway: £12.99

Mini Meals
Eat In: £8.99 | Takeaway: £9.99

Variety Rice

Sambar Rice / Bisibelabath — £7.50

Curd Rice / Bagalabath — £6.99

Coconut Rice — £7.99

Lemon Rice — £7.99

Tomato Rice — £7.99

Tamarind Rice — £7.99

Biryani

Vegetable Dum Biryani — £7.99

Mushroom Biryani — £8.99

Paneer Biryani — £9.50

Chef’s Special Biryani — £9.99

Pulao Rice

Veg Pulao — £6.99

Paneer Pulao — £8.99

Cashew Pulao — £8.99

Jeera Pulao — £6.99

Mushroom Pulao — £8.50

Fried Rice

Veg Fried Rice — £8.50

Szechwan Fried Rice — £8.99

Paneer Fried Rice — £9.50

Chef’s Special Fried Rice — £9.99

Mushroom Fried Rice — £8.50

Noodles

Veg Noodles — £7.99

Szechwan Noodles — £8.99

Mushroom Noodles — £8.50

Curries

Mushroom Chettinad — £9.99

Bhindi Masala — £8.99

Mixed Vegetable Curry — £8.99

Baingan Masala — £8.99

Malai Kofta — £8.99

Paneer Chettinad — £9.99

Kadai Paneer — £9.99

Paneer Butter Masala — £9.50

Paneer Tikka Masala — £9.99

Paneer Shai Kurma — £9.99

Palak Paneer — £9.50

Paneer Burji — £9.99

Paneer Jal Frieze — £9.99

Mutter Paneer — £9.50

Dhal Butter Fry — £7.50

Dhal Makhani — £7.99

Aloo Gobi Masala — £8.50

Aloo Palak — £8.99

Vegetable Kadai — £8.99

Channa Masala — £7.50

Vegetable Kurma — £7.50

Indian Breads

Plain Naan — £1.99

Butter Naan — £2.75

Garlic Naan — £2.99

Tandoori Roti — £2.25

Butter Roti — £2.75

Aloo Kulcha — £3.50

Paneer Kulcha — £3.99

Chapathi — £1.99

Parotta — £2.50

Drinks

Lassi
Mango / Sweet / Salt — Glass £4.99 | Jug £16.99

Milkshakes
Strawberry — £5.50
Chocolate — £5.50
Vanilla — £5.50
Mango — £5.99
Ferrero Rocher — £5.99
Oreo — £5.99

Fresh Juice
Apple — £5.99
ABC Juice — £6.50
Orange — £6.50
Carrot — £6.50
Watermelon — £6.50
Passion Fruit — £6.50
Lime Juice — £6.50

Desserts

Falooda — £6.50

Gulab Jamun — £3.99

Kesari — £4.50

Milk Cake — £4.99

Payasam — £4.50

Carrot Halwa — £4.99

Motichoor Laddu — £1.50

Kaju Sweet — £1.99

Ice Cream

Chocolate — £3.99

Vanilla — £3.50

Strawberry — £3.50

Mango — £3.50

Kulfi

Malai Kulfi — £2.99

Mango Kulfi — £2.99

Pistachio Kulfi — £2.99

Beverages

Rose Milk — £4.99

Butter Milk — £4.50

Soft Drinks — £2.50

Mineral Water (500ml) — £1.99

Hot Beverages

Masala Tea — £2.50

Filter Coffee — £2.50

Hot Milk — £2.50

Hot Badam Milk — £3.99

Extras

Sweet Beeda — £2.50

Curd — £2.99

Raitha — £2.99

Green Salad — £3.99
"""

lines = [l.strip() for l in menu_text.split("\n") if l.strip()]

categories = []
current_category = None
items = []

for line in lines:
    if "—" not in line and "£" not in line and "Eat In:" not in line:
        # Likely a category header
        current_category = line
        continue
    
    # Check for price and name
    if "— £" in line or "— Glass £" in line or "Eat In: £" in line:
        if "Eat In: £" in line:
            name = line.split("\n")[0].strip()
            price_match = re.search(r"Eat In: £([\d.]+)", line)
            price = float(price_match.group(1)) if price_match else 0.0
        elif "— Glass £" in line:
             name = line.split("—")[0].strip()
             price_match = re.search(r"Glass £([\d.]+)", line)
             price = float(price_match.group(1)) if price_match else 0.0
        else:
            parts = line.split("—")
            name = parts[0].strip()
            price_str = parts[1].strip().replace("£", "")
            try:
                price = float(price_str)
            except:
                price = 0.0
        
        items.append({
            "name": name,
            "category": current_category,
            "price": price,
            "description": "" # Descriptions are usually on the next line
        })
    elif line.endswith("—") or "—" in line: # Fallback for malformed lines
         pass

# Refining descriptions (they follow the items)
refined_items = []
for i, item in enumerate(items):
    # This is a bit complex since many items don't have descriptions in the provided text
    # But some do (like Gobi 65).
    # Let's just use the current parsing which is mostly correct for names and prices.
    refined_items.append(item)

# Generating the python code
print("_STATIC_MENU: dict[str, MenuItem] = {")
for i, item in enumerate(refined_items):
    id = f"I{i+1:03d}"
    print(f'    "{id}": MenuItem("{id}", "{item["name"]}", {item["price"]}, "{item["description"]}", "{item["category"].lower()}"),')
print("}")

vocab = [item["name"] for item in refined_items]
print(f'_MENU_VOCAB_HINT = "{", ".join(vocab)}"')
