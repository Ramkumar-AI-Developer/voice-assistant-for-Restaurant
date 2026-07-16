import { createSlice } from '@reduxjs/toolkit';

const DEFAULT_MENU = [
  // Soup Bowl
  { id: 'SB01', name: 'Hot & Sour Veg Soup', price: 548.90, description: 'Hot and spicy thick soup made with sautéed fresh vegetables and soy sauce.', category: 'Soup Bowl', available: true, customisations: [] },
  { id: 'SB02', name: 'Sweet Corn Soup', price: 548.90, description: 'Lightly spiced corn soup flavoured with pepper.', category: 'Soup Bowl', available: true, customisations: [] },
  { id: 'SB03', name: 'Mushroom Soup', price: 548.90, description: 'Lightly spiced minced mushroom soup garnished with cream.', category: 'Soup Bowl', available: true, customisations: [] },
  { id: 'SB04', name: 'Pepper Rasam Soup', price: 495.00, description: 'Traditional South Indian sour & spicy soup with diced fresh tomatoes & tamarind juice.', category: 'Soup Bowl', available: true, customisations: [] },

  // Starters
  { id: 'ST01', name: 'Gobi 65', price: 935.00, description: 'Battered cauliflower florets deep fried with spices and chilli paste.', category: 'Starters', available: true, customisations: [] },
  { id: 'ST02', name: 'Paneer 65', price: 988.90, description: 'Batter deep fried Indian cottage cheese chunks flavoured with spicy paste.', category: 'Starters', available: true, customisations: [] },
  { id: 'ST03', name: 'Mogo 65', price: 878.90, description: 'Casava marinated in Indian & Chinese spices, dipped in gram flour batter & deep fried.', category: 'Starters', available: true, customisations: [] },
  { id: 'ST04', name: 'Mushroom 65', price: 878.90, description: 'Battered fried mushroom sautéed with spices & chilli paste.', category: 'Starters', available: true, customisations: [] },
  { id: 'ST05', name: 'Paneer Tikka', price: 1098.90, description: 'Chunks of cottage cheese marinated in special herbs & spices & grilled in a clay oven.', category: 'Starters', available: true, customisations: [] },
  { id: 'ST06', name: 'Paneer Pepper Fry', price: 1045.00, description: 'Chunks of cottage cheese batter fried & sautéed with flavoured spices & pepper.', category: 'Starters', available: true, customisations: [] },
  { id: 'ST07', name: 'Mushroom Pepper Fry', price: 988.90, description: 'Mushroom batter fried & sautéed with flavoured spices & pepper.', category: 'Starters', available: true, customisations: [] },
  { id: 'ST08', name: 'Chilly Paneer', price: 988.90, description: 'Cottage cheese diced marinated in an authentic South Indian chilli mix & pan cooked.', category: 'Starters', available: true, customisations: ['dry', 'gravy'] },
  { id: 'ST09', name: 'Chilly Baby Corn', price: 988.90, description: 'Baby corn diced marinated in an authentic South Indian chilli mix & pan cooked.', category: 'Starters', available: true, customisations: ['dry', 'gravy'] },
  { id: 'ST10', name: 'Chilly Mogo', price: 962.50, description: 'Steamed tapioca pieces deep fried and tossed in chef\'s special chilli sauce & spices.', category: 'Starters', available: true, customisations: ['dry', 'gravy'] },
  { id: 'ST11', name: 'Chilly Gobi', price: 935.00, description: 'Steamed cauliflower pieces deep fried and tossed in chef\'s special chilli sauce & spices.', category: 'Starters', available: true, customisations: ['dry', 'gravy'] },
  { id: 'ST12', name: 'Veg Manchurian', price: 988.90, description: 'Minced vegetables deep fried in balls sautéed with onion & garlic in Manchurian sauce.', category: 'Starters', available: true, customisations: ['dry', 'gravy'] },
  { id: 'ST13', name: 'Paneer Manchurian', price: 988.90, description: '', category: 'Starters', available: true, customisations: ['dry', 'gravy'] },
  { id: 'ST14', name: 'Gobi Manchurian', price: 935.00, description: '', category: 'Starters', available: true, customisations: ['dry', 'gravy'] },
  { id: 'ST15', name: 'Mushroom Manchurian', price: 935.00, description: '', category: 'Starters', available: true, customisations: ['dry', 'gravy'] },
  { id: 'ST16', name: 'Veg Roll (2 pcs)', price: 548.90, description: '', category: 'Starters', available: true, customisations: [] },
  { id: 'ST17', name: 'Veg Samosa (3 pcs)', price: 495.00, description: '', category: 'Starters', available: true, customisations: [] },
  { id: 'ST18', name: 'Onion Pakoda', price: 495.00, description: '', category: 'Starters', available: true, customisations: [] },
  { id: 'ST19', name: 'Vegetable Spring Roll (3 pcs)', price: 495.00, description: '', category: 'Starters', available: true, customisations: [] },
  { id: 'ST20', name: 'Plain Papadum', price: 165.00, description: '', category: 'Starters', available: true, customisations: [] },
  { id: 'ST21', name: 'Masala Papadum', price: 385.00, description: '', category: 'Starters', available: true, customisations: [] },
  { id: 'ST22', name: 'Chilly Idly', price: 935.00, description: '', category: 'Starters', available: true, customisations: [] },
  { id: 'ST23', name: 'Cocktail Idly', price: 825.00, description: '', category: 'Starters', available: true, customisations: [] },
  { id: 'ST24', name: 'Mini Podi Idly', price: 768.90, description: '', category: 'Starters', available: true, customisations: [] },

  // Chaat
  { id: 'CH01', name: 'Samosa Chaat', price: 768.90, description: '', category: 'Chaat', available: true, customisations: [] },
  { id: 'CH02', name: 'Panipuri', price: 658.90, description: '', category: 'Chaat', available: true, customisations: [] },
  { id: 'CH03', name: 'Dahi Batata Puri', price: 658.90, description: '', category: 'Chaat', available: true, customisations: [] },
  { id: 'CH04', name: 'Aloo Papdi Chaat', price: 768.90, description: '', category: 'Chaat', available: true, customisations: [] },

  // Vada
  { id: 'VA01', name: 'Medhu Vada (2 pcs)', price: 495.00, description: '', category: 'Vada', available: true, customisations: [] },
  { id: 'VA02', name: 'Sambar Vada (2 pcs)', price: 658.90, description: '', category: 'Vada', available: true, customisations: [] },
  { id: 'VA03', name: 'Rasa Vada (2 pcs)', price: 658.90, description: '', category: 'Vada', available: true, customisations: [] },
  { id: 'VA04', name: 'Thayir Vada (2 pcs)', price: 658.90, description: '', category: 'Vada', available: true, customisations: [] },

  // Idly
  { id: 'ID01', name: 'Idly (3 pcs)', price: 605.00, description: '', category: 'Idly', available: true, customisations: [] },
  { id: 'ID02', name: 'Idly (2 pcs) & Vada (1 pc)', price: 605.00, description: '', category: 'Idly', available: true, customisations: [] },
  { id: 'ID03', name: 'Sambar Idly (2 pcs)', price: 658.90, description: '', category: 'Idly', available: true, customisations: [] },
  { id: 'ID04', name: 'Mini Ghee Idly', price: 658.90, description: '', category: 'Idly', available: true, customisations: [] },
  { id: 'ID05', name: 'Podi Idly', price: 715.00, description: '', category: 'Idly', available: true, customisations: [] },

  // South Indian Corner
  { id: 'SI01', name: 'Ghee Pongal', price: 825.00, description: '', category: 'South Indian Corner', available: true, customisations: [] },
  { id: 'SI02', name: 'Pongal & Vada', price: 878.90, description: '', category: 'South Indian Corner', available: true, customisations: [] },
  { id: 'SI03', name: 'Poori (2 pcs) Masala', price: 768.90, description: '', category: 'South Indian Corner', available: true, customisations: [] },
  { id: 'SI04', name: 'Chappathi (2 pcs) with Kurma', price: 768.90, description: '', category: 'South Indian Corner', available: true, customisations: [] },
  { id: 'SI05', name: 'Parotta (2 pcs) with Kurma', price: 878.90, description: '', category: 'South Indian Corner', available: true, customisations: [] },
  { id: 'SI06', name: 'Channa Bhatura', price: 878.90, description: '', category: 'South Indian Corner', available: true, customisations: [] },
  { id: 'SI07', name: 'Chilli Parotta', price: 988.90, description: '', category: 'South Indian Corner', available: true, customisations: [] },
  { id: 'SI08', name: 'Kothu Parotta', price: 988.90, description: '', category: 'South Indian Corner', available: true, customisations: [] },

  // Dosas
  { id: 'DO01', name: 'Plain Dosa', price: 605.00, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO02', name: 'Masala Dosa', price: 768.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO03', name: 'Onion Dosa', price: 715.00, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO04', name: 'Onion Masala Dosa', price: 878.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO05', name: 'Ghee Roast', price: 878.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO06', name: 'Ghee Masala Roast', price: 988.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO07', name: 'Butter Dosa', price: 878.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO08', name: 'Butter Masala Dosa', price: 988.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO09', name: 'Paper Roast', price: 935.00, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO10', name: 'Paper Masala Roast', price: 1098.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO11', name: 'Kal Dosa (2 pcs)', price: 878.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO12', name: 'Podi Dosa', price: 825.00, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO13', name: 'Podi Masala Dosa', price: 988.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO14', name: 'Kara Podi Dosa', price: 935.00, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO15', name: 'Kara Podi Masala Dosa', price: 1098.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO16', name: 'Mysore Dosa', price: 825.00, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO17', name: 'Mysore Masala Dosa', price: 988.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO18', name: 'Paneer Masala Dosa', price: 1098.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO19', name: 'Mushroom Masala Dosa', price: 1098.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO20', name: 'Veg Masala Dosa', price: 1098.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO21', name: 'VV Special Dosa', price: 1208.90, description: '', category: 'Dosas', available: true, customisations: [] },
  { id: 'DO22', name: 'Family Dosa', price: 1868.90, description: '', category: 'Dosas', available: true, customisations: [] },

  // Meals
  { id: 'ME01', name: 'South Indian Meals', price: 1208.90, description: 'Eat In ₹1208.90 / Takeaway ₹1428.90 Full South Indian meal with rice, curries & accompaniments.', category: 'Meals', available: true, customisations: ['eat in', 'takeaway'] },
  { id: 'ME02', name: 'North Indian Meals', price: 1208.90, description: 'Eat In ₹1208.90 / Takeaway ₹1428.90 Full North Indian meal with rice, curries & accompaniments.', category: 'Meals', available: true, customisations: ['eat in', 'takeaway'] },
  { id: 'ME03', name: 'Mini Meals', price: 988.90, description: 'Eat In ₹988.90 / Takeaway ₹1098.90 Smaller meal with rice, curry & accompaniments.', category: 'Meals', available: true, customisations: ['eat in', 'takeaway'] },

  // Variety Rice
  { id: 'VR01', name: 'Sambar Rice / Bisibelabath', price: 825.00, description: '', category: 'Variety Rice', available: true, customisations: [] },
  { id: 'VR02', name: 'Curd Rice / Bagalabath', price: 768.90, description: '', category: 'Variety Rice', available: true, customisations: [] },
  { id: 'VR03', name: 'Coconut Rice', price: 878.90, description: '', category: 'Variety Rice', available: true, customisations: [] },
  { id: 'VR04', name: 'Lemon Rice', price: 878.90, description: '', category: 'Variety Rice', available: true, customisations: [] },
  { id: 'VR05', name: 'Tomato Rice', price: 878.90, description: '', category: 'Variety Rice', available: true, customisations: [] },
  { id: 'VR06', name: 'Tamarind Rice', price: 878.90, description: '', category: 'Variety Rice', available: true, customisations: [] },

  // Biryani
  { id: 'BI01', name: 'Vegetable Dum Biryani', price: 878.90, description: '', category: 'Biryani', available: true, customisations: [] },
  { id: 'BI02', name: 'Mushroom Biryani', price: 988.90, description: '', category: 'Biryani', available: true, customisations: [] },
  { id: 'BI03', name: 'Paneer Biryani', price: 1045.00, description: '', category: 'Biryani', available: true, customisations: [] },
  { id: 'BI04', name: 'Chef\'s Special Biryani', price: 1098.90, description: '', category: 'Biryani', available: true, customisations: [] },

  // Drinks
  { id: 'DR01', name: 'Lassi (Mango)', price: 548.90, description: 'Mango lassi — glass.', category: 'Drinks', available: true, customisations: ['mango', 'sweet', 'salt'] },
  { id: 'DR02', name: 'Lassi (Jug)', price: 1868.90, description: 'Lassi jug.', category: 'Drinks', available: true, customisations: ['mango', 'sweet', 'salt'] },
  { id: 'DR03', name: 'Strawberry Milkshake', price: 605.00, description: '', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR04', name: 'Chocolate Milkshake', price: 605.00, description: '', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR05', name: 'Vanilla Milkshake', price: 605.00, description: '', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR06', name: 'Mango Milkshake', price: 658.90, description: '', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR07', name: 'Ferrero Rocher Milkshake', price: 658.90, description: '', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR08', name: 'Oreo Milkshake', price: 658.90, description: '', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR09', name: 'Apple Juice', price: 658.90, description: 'Fresh juice.', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR10', name: 'ABC Juice', price: 715.00, description: 'Fresh apple, beetroot & carrot juice.', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR11', name: 'Orange Juice', price: 715.00, description: 'Fresh juice.', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR12', name: 'Carrot Juice', price: 715.00, description: 'Fresh juice.', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR13', name: 'Watermelon Juice', price: 715.00, description: 'Fresh juice.', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR14', name: 'Passion Fruit Juice', price: 715.00, description: 'Fresh juice.', category: 'Drinks', available: true, customisations: [] },
  { id: 'DR15', name: 'Lime Juice', price: 715.00, description: 'Fresh juice.', category: 'Drinks', available: true, customisations: [] },

  // Desserts
  { id: 'DE01', name: 'Falooda', price: 715.00, description: '', category: 'Desserts', available: true, customisations: [] },
  { id: 'DE02', name: 'Gulab Jamun', price: 438.90, description: '', category: 'Desserts', available: true, customisations: [] },
  { id: 'DE03', name: 'Kesari', price: 495.00, description: '', category: 'Desserts', available: true, customisations: [] },
  { id: 'DE04', name: 'Milk Cake', price: 548.90, description: '', category: 'Desserts', available: true, customisations: [] },
  { id: 'DE05', name: 'Payasam', price: 495.00, description: '', category: 'Desserts', available: true, customisations: [] },
  { id: 'DE06', name: 'Carrot Halwa', price: 548.90, description: '', category: 'Desserts', available: true, customisations: [] },
  { id: 'DE07', name: 'Motichoor Laddu', price: 165.00, description: '', category: 'Desserts', available: true, customisations: [] },
  { id: 'DE08', name: 'Kaju Sweet', price: 218.90, description: '', category: 'Desserts', available: true, customisations: [] },

  // Ice Cream
  { id: 'IC01', name: 'Chocolate Ice Cream', price: 438.90, description: '', category: 'Ice Cream', available: true, customisations: [] },
  { id: 'IC02', name: 'Vanilla Ice Cream', price: 385.00, description: '', category: 'Ice Cream', available: true, customisations: [] },
  { id: 'IC03', name: 'Strawberry Ice Cream', price: 385.00, description: '', category: 'Ice Cream', available: true, customisations: [] },
  { id: 'IC04', name: 'Mango Ice Cream', price: 385.00, description: '', category: 'Ice Cream', available: true, customisations: [] },

  // Beverages
  { id: 'BV01', name: 'Rose Milk', price: 548.90, description: '', category: 'Beverages', available: true, customisations: [] },
  { id: 'BV02', name: 'Butter Milk', price: 495.00, description: '', category: 'Beverages', available: true, customisations: [] },
  { id: 'BV03', name: 'Soft Drinks', price: 275.00, description: '', category: 'Beverages', available: true, customisations: [] },
  { id: 'BV04', name: 'Mineral Water (500ml)', price: 218.90, description: '', category: 'Beverages', available: true, customisations: [] },

  // Hot Beverages
  { id: 'HB01', name: 'Masala Tea', price: 275.00, description: '', category: 'Hot Beverages', available: true, customisations: [] },
  { id: 'HB02', name: 'Filter Coffee', price: 275.00, description: '', category: 'Hot Beverages', available: true, customisations: [] },
  { id: 'HB03', name: 'Hot Milk', price: 275.00, description: '', category: 'Hot Beverages', available: true, customisations: [] },
  { id: 'HB04', name: 'Hot Badam Milk', price: 438.90, description: '', category: 'Hot Beverages', available: true, customisations: [] },

  // Extras
  { id: 'EX01', name: 'Sweet Beeda', price: 275.00, description: '', category: 'Extras', available: true, customisations: [] },
  { id: 'EX02', name: 'Curd', price: 328.90, description: '', category: 'Extras', available: true, customisations: [] },
  { id: 'EX03', name: 'Raitha', price: 328.90, description: '', category: 'Extras', available: true, customisations: [] },
  { id: 'EX04', name: 'Green Salad', price: 438.90, description: '', category: 'Extras', available: true, customisations: [] },
];

const getStoredMenu = () => {
  const menu = localStorage.getItem('demo_menu');
  if (menu) return JSON.parse(menu);
  localStorage.setItem('demo_menu', JSON.stringify(DEFAULT_MENU));
  return DEFAULT_MENU;
};

const menuSlice = createSlice({
  name: 'menu',
  initialState: {
    items: getStoredMenu(),
  },
  reducers: {
    addItem: (state, action) => {
      const newItem = {
        id: action.payload.id || `ITEM${Date.now()}`,
        name: action.payload.name,
        price: parseFloat(action.payload.price),
        description: action.payload.description || '',
        category: action.payload.category,
        available: action.payload.available !== false,
        customisations: action.payload.customisations || [],
      };
      state.items.push(newItem);
      localStorage.setItem('demo_menu', JSON.stringify(state.items));
    },
    updateItem: (state, action) => {
      const index = state.items.findIndex(item => item.id === action.payload.id);
      if (index !== -1) {
        state.items[index] = {
          ...state.items[index],
          ...action.payload,
          price: parseFloat(action.payload.price),
        };
        localStorage.setItem('demo_menu', JSON.stringify(state.items));
      }
    },
    deleteItem: (state, action) => {
      state.items = state.items.filter(item => item.id !== action.payload);
      localStorage.setItem('demo_menu', JSON.stringify(state.items));
    },
    bulkDeleteItems: (state, action) => {
      const idsToDelete = action.payload;
      state.items = state.items.filter(item => !idsToDelete.includes(item.id));
      localStorage.setItem('demo_menu', JSON.stringify(state.items));
    },
    importMenu: (state, action) => {
      // action.payload is a list of parsed CSV items
      const imported = action.payload.map((item, index) => ({
        id: item.id || `IMP${Date.now()}${index}`,
        name: item.name,
        price: parseFloat(item.price) || 0,
        description: item.description || '',
        category: item.category || 'Uncategorized',
        available: item.available !== 'No' && item.available !== false,
        customisations: typeof item.customisations === 'string'
          ? item.customisations.split(';').map(c => c.trim()).filter(Boolean)
          : Array.isArray(item.customisations) ? item.customisations : [],
      }));

      // Merge: replace if same name, else add
      imported.forEach(newItm => {
        const idx = state.items.findIndex(existing => existing.name.toLowerCase() === newItm.name.toLowerCase());
        if (idx !== -1) {
          state.items[idx] = { ...state.items[idx], ...newItm, id: state.items[idx].id };
        } else {
          state.items.push(newItm);
        }
      });
      localStorage.setItem('demo_menu', JSON.stringify(state.items));
    },
  },
});

export const { addItem, updateItem, deleteItem, bulkDeleteItems, importMenu } = menuSlice.actions;
export default menuSlice.reducer;
