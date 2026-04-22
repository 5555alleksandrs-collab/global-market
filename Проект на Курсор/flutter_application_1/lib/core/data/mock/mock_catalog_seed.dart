import '../../domain/models/brand.dart';
import '../../domain/models/category.dart';
import '../../domain/models/product.dart';
import '../../domain/models/product_variant.dart';
import '../../domain/models/tech_specs.dart';

/// Статические категории магазина.
List<Category> seedCategories() => const [
      Category(id: 'iphone', name: 'iPhone', subtitle: 'Apple', iconName: 'phone_iphone'),
      Category(id: 'airpods', name: 'AirPods', subtitle: 'Apple', iconName: 'headphones'),
      Category(id: 'apple_watch', name: 'Apple Watch', subtitle: 'Apple', iconName: 'watch'),
      Category(id: 'dyson', name: 'Dyson', subtitle: 'Техника для дома', iconName: 'air'),
      Category(id: 'macbook', name: 'MacBook', subtitle: 'Apple', iconName: 'laptop_mac'),
      Category(id: 'ipad', name: 'iPad', subtitle: 'Apple', iconName: 'tablet_mac'),
      Category(id: 'samsung', name: 'Samsung', subtitle: 'Galaxy', iconName: 'android'),
      Category(id: 'accessories', name: 'Accessories', subtitle: 'Аксессуары', iconName: 'cable'),
      Category(id: 'sony', name: 'Sony', subtitle: 'PlayStation & audio', iconName: 'sports_esports'),
      Category(id: 'instax', name: 'instax', subtitle: 'Моментальная печать', iconName: 'photo_camera'),
      Category(id: 'steam_deck_oled', name: 'STEAM DECK OLED', subtitle: 'Портативный PC', iconName: 'videogame_asset'),
      Category(id: 'nintendo_switch_2', name: 'Nintendo Switch 2', subtitle: 'Консоль', iconName: 'games'),
      Category(id: 'meta_quest', name: 'Meta Quest', subtitle: 'VR', iconName: 'view_in_ar'),
      Category(id: 'bose', name: 'Bose', subtitle: 'Аудио', iconName: 'speaker'),
      Category(id: 'dji', name: 'DJI', subtitle: 'Дроны и стабилизация', iconName: 'flight'),
      Category(id: 'garmin', name: 'Garmin', subtitle: 'Спорт и GPS', iconName: 'directions_run'),
      Category(id: 'gopro', name: 'GoPro', subtitle: 'Экшн-камеры', iconName: 'movie'),
      Category(id: 'marshall', name: 'Marshall', subtitle: 'Аудио', iconName: 'music_note'),
    ];

List<Brand> seedBrands() => const [
      Brand(id: 'apple', name: 'Apple'),
      Brand(id: 'samsung', name: 'Samsung'),
      Brand(id: 'dyson', name: 'Dyson'),
      Brand(id: 'sony', name: 'Sony'),
      Brand(id: 'fujifilm', name: 'Fujifilm'),
      Brand(id: 'valve', name: 'Valve'),
      Brand(id: 'nintendo', name: 'Nintendo'),
      Brand(id: 'meta', name: 'Meta'),
      Brand(id: 'bose', name: 'Bose'),
      Brand(id: 'dji', name: 'DJI'),
      Brand(id: 'garmin', name: 'Garmin'),
      Brand(id: 'gopro', name: 'GoPro'),
      Brand(id: 'marshall', name: 'Marshall'),
      Brand(id: 'belkin', name: 'Belkin'),
      Brand(id: 'anker', name: 'Anker'),
    ];

String _img(String seed) =>
    'https://picsum.photos/seed/${Uri.encodeComponent(seed)}/900/1100';

List<ProductVariant> _iphoneVariants(String pid, double base) {
  final colors = ['Natural Titanium', 'Black Titanium', 'White Titanium'];
  final storages = ['256 ГБ', '512 ГБ', '1 ТБ'];
  final regions = ['RU', 'EU'];
  final sims = ['eSIM', 'eSIM + nano-SIM'];
  var i = 0;
  final out = <ProductVariant>[];
  for (final s in storages) {
    for (final c in colors) {
      for (final r in regions) {
        for (final sim in sims) {
          i++;
          final price = base + (s.contains('512') ? 20000 : 0) + (s.contains('1 ТБ') ? 45000 : 0);
          out.add(
            ProductVariant(
              id: '$pid-v$i',
              sku: '${pid.toUpperCase()}-$i',
              label: '$s · $c · $r · $sim',
              attributes: {
                'Память': s,
                'Цвет': c,
                'Регион': r,
                'SIM': sim,
              },
              price: price,
              oldPrice: price + 15000,
              inStock: i % 5 != 0,
            ),
          );
        }
      }
    }
  }
  return out.take(8).toList();
}

List<ProductVariant> _macVariants(String pid, double base) {
  return [
    ProductVariant(
      id: '$pid-v1',
      sku: '${pid.toUpperCase()}-1',
      label: '13" · M4 · 16 ГБ · Midnight',
      attributes: {'Диагональ': '13"', 'Чип': 'M4', 'Память': '16 ГБ', 'Цвет': 'Midnight'},
      price: base,
      oldPrice: base + 12000,
      inStock: true,
    ),
    ProductVariant(
      id: '$pid-v2',
      sku: '${pid.toUpperCase()}-2',
      label: '15" · M4 Pro · 24 ГБ · Silver',
      attributes: {'Диагональ': '15"', 'Чип': 'M4 Pro', 'Память': '24 ГБ', 'Цвет': 'Silver'},
      price: base + 80000,
      oldPrice: base + 95000,
      inStock: true,
    ),
  ];
}

List<ProductVariant> _watchVariants(String pid, double base) {
  return [
    ProductVariant(
      id: '$pid-v1',
      sku: '${pid.toUpperCase()}-1',
      label: '45 мм · Jet Black',
      attributes: {'Размер': '45 мм', 'Цвет': 'Jet Black'},
      price: base,
      inStock: true,
    ),
    ProductVariant(
      id: '$pid-v2',
      sku: '${pid.toUpperCase()}-2',
      label: '49 мм · Natural Titanium',
      attributes: {'Размер': '49 мм', 'Цвет': 'Natural Titanium'},
      price: base + 25000,
      inStock: true,
    ),
  ];
}

List<ProductVariant> _airpodsVariants(String pid, double base) {
  return [
    ProductVariant(
      id: '$pid-v1',
      sku: '${pid.toUpperCase()}-1',
      label: 'AirPods 4',
      attributes: {'Модель': 'AirPods 4'},
      price: base - 15000,
      inStock: true,
    ),
    ProductVariant(
      id: '$pid-v2',
      sku: '${pid.toUpperCase()}-2',
      label: 'AirPods Pro 3',
      attributes: {'Модель': 'AirPods Pro 3'},
      price: base,
      oldPrice: base + 5000,
      inStock: true,
    ),
  ];
}

List<ProductVariant> _samsungVariants(String pid, double base) {
  return [
    ProductVariant(
      id: '$pid-v1',
      sku: '${pid.toUpperCase()}-1',
      label: '256 ГБ · Phantom Black',
      attributes: {'Память': '256 ГБ', 'Цвет': 'Phantom Black'},
      price: base,
      inStock: true,
    ),
    ProductVariant(
      id: '$pid-v2',
      sku: '${pid.toUpperCase()}-2',
      label: '512 ГБ · Titanium Gray',
      attributes: {'Память': '512 ГБ', 'Цвет': 'Titanium Gray'},
      price: base + 25000,
      inStock: true,
    ),
  ];
}

List<ProductVariant> _switch2Variants(String pid, double base) {
  return [
    ProductVariant(
      id: '$pid-v1',
      sku: '${pid.toUpperCase()}-1',
      label: 'Стандарт',
      attributes: {'Комплектация': 'Стандарт'},
      price: base,
      inStock: true,
    ),
    ProductVariant(
      id: '$pid-v2',
      sku: '${pid.toUpperCase()}-2',
      label: 'С игра Mario Kart World',
      attributes: {'Комплектация': 'С игра Mario Kart World'},
      price: base + 7000,
      inStock: true,
    ),
  ];
}

List<ProductVariant> _genericColorModel(String pid, double base, String brandLabel) {
  return [
    ProductVariant(
      id: '$pid-v1',
      sku: '${pid.toUpperCase()}-1',
      label: '$brandLabel · Чёрный · Стандарт',
      attributes: {'Модель': brandLabel, 'Цвет': 'Чёрный', 'Версия': 'Стандарт'},
      price: base,
      inStock: true,
    ),
    ProductVariant(
      id: '$pid-v2',
      sku: '${pid.toUpperCase()}-2',
      label: '$brandLabel · Серебро · Pro',
      attributes: {'Модель': brandLabel, 'Цвет': 'Серебро', 'Версия': 'Pro'},
      price: base + 12000,
      inStock: true,
    ),
  ];
}

TechSpecs _specsFor(String cat) {
  switch (cat) {
    case 'iphone':
      return const TechSpecs(
        chipset: 'A19 Pro',
        displaySize: '6.3" Super Retina XDR',
        battery: 'До 29 ч видео',
        connectivity: '5G, Wi‑Fi 7, Bluetooth 6',
        warranty: '1 год',
      );
    case 'macbook':
      return const TechSpecs(
        chipset: 'Apple M4',
        displaySize: '13.6" Liquid Retina',
        battery: 'До 18 ч',
        connectivity: 'Wi‑Fi 6E, Thunderbolt',
        warranty: '1 год',
      );
    case 'ipad':
      return const TechSpecs(
        chipset: 'M2',
        displaySize: '11" Liquid Retina',
        battery: 'До 10 ч',
        connectivity: 'Wi‑Fi 6E, USB‑C',
        warranty: '1 год',
      );
    case 'steam_deck_oled':
      return const TechSpecs(
        displaySize: '7.4" OLED HDR',
        battery: '50 Вт·ч',
        connectivity: 'Wi‑Fi 6E, Bluetooth 5.3',
        warranty: '1 год',
      );
    case 'meta_quest':
      return const TechSpecs(
        displaySize: '2064×2208 на глаз',
        battery: 'До 2.2 ч активного VR',
        connectivity: 'Wi‑Fi 6E',
        warranty: '1 год',
      );
    default:
      return const TechSpecs(warranty: '1 год', condition: 'Новый');
  }
}

Map<String, String> _mapFor(String cat, String name) {
  return {
    'Серия': name,
    'Категория': cat,
  };
}

List<ProductVariant> _variants(String cat, String pid, double price, String name) {
  switch (cat) {
    case 'iphone':
      return _iphoneVariants(pid, price);
    case 'macbook':
      return _macVariants(pid, price);
    case 'apple_watch':
      return _watchVariants(pid, price);
    case 'airpods':
      return _airpodsVariants(pid, price);
    case 'samsung':
      return _samsungVariants(pid, price);
    case 'nintendo_switch_2':
      return _switch2Variants(pid, price);
    case 'dyson':
    case 'dji':
    case 'gopro':
    case 'bose':
    case 'marshall':
      return _genericColorModel(pid, price, name);
    default:
      return [
        ProductVariant(
          id: '$pid-v1',
          sku: '${pid.toUpperCase()}-1',
          label: 'Стандартная комплектация',
          attributes: const {'Комплектация': 'Стандарт'},
          price: price,
          inStock: true,
        ),
      ];
  }
}

/// Имена товаров по категориям (≥4 позиции).
const _productNames = <String, List<String>>{
  'iphone': ['iPhone 17', 'iPhone 17 Pro', 'iPhone 17 Pro Max', 'iPhone 16'],
  'airpods': ['AirPods 4', 'AirPods Pro 3', 'AirPods Max USB‑C', 'AirPods 3'],
  'apple_watch': ['Apple Watch Series 11', 'Apple Watch Ultra 3', 'Apple Watch SE 3', 'Apple Watch Hermès'],
  'dyson': ['Supersonic Nural', 'Airwrap i.d.', 'V15s Detect Submarine', 'Purifier Big+Quiet'],
  'macbook': ['MacBook Air 13" M4', 'MacBook Pro 14" M4 Pro', 'MacBook Air 15" M3', 'MacBook Pro 16" M4 Max'],
  'ipad': ['iPad Pro 11" M4', 'iPad Air M2', 'iPad mini A17 Pro', 'iPad 11" A16'],
  'samsung': ['Galaxy S25 Ultra', 'Galaxy Z Fold 7', 'Galaxy S25+', 'Galaxy Tab S10 Ultra'],
  'accessories': ['MagSafe Charger 25W', 'USB‑C Cable 2m', 'AirTag 4‑pack', 'Belkin Stand'],
  'sony': ['PlayStation 5 Pro', 'WH‑1000XM6', 'Pulse Elite', 'INZONE Buds'],
  'instax': ['instax mini 12', 'instax SQ40', 'instax WIDE 400', 'instax mini Evo'],
  'steam_deck_oled': ['Steam Deck OLED 512GB', 'Steam Deck OLED 1TB', 'Steam Deck OLED Limited', 'Steam Deck Dock'],
  'nintendo_switch_2': ['Nintendo Switch 2', 'Switch 2 + Mario Kart', 'Switch 2 Pro Controller bundle', 'Switch 2 Case Pack'],
  'meta_quest': ['Meta Quest 3 128GB', 'Meta Quest 3 512GB', 'Meta Quest 3S', 'Elite Strap Bundle'],
  'bose': ['QuietComfort Ultra Earbuds', 'QuietComfort Headphones', 'SoundLink Flex 2', 'Ultra Open Earbuds'],
  'dji': ['DJI Osmo Pocket 3', 'DJI Mini 4 Pro', 'DJI Mic 3', 'DJI Osmo Action 5 Pro'],
  'garmin': ['fēnix 8 47mm', 'Forerunner 965', 'Venu 3', 'Instinct 3'],
  'gopro': ['HERO13 Black', 'HERO12 Black', 'MAX 2', 'HERO11 Mini'],
  'marshall': ['Major V', 'Emberton III', 'Acton III', 'Monitor III A.N.C.'],
};

String _brandIdForCategory(String cat) {
  switch (cat) {
    case 'iphone':
    case 'airpods':
    case 'apple_watch':
    case 'macbook':
    case 'ipad':
      return 'apple';
    case 'samsung':
      return 'samsung';
    case 'dyson':
      return 'dyson';
    case 'sony':
      return 'sony';
    case 'instax':
      return 'fujifilm';
    case 'steam_deck_oled':
      return 'valve';
    case 'nintendo_switch_2':
      return 'nintendo';
    case 'meta_quest':
      return 'meta';
    case 'bose':
      return 'bose';
    case 'dji':
      return 'dji';
    case 'garmin':
      return 'garmin';
    case 'gopro':
      return 'gopro';
    case 'marshall':
      return 'marshall';
    case 'accessories':
      return 'belkin';
    default:
      return 'apple';
  }
}

/// Полный mock-каталог.
List<Product> seedProducts() {
  final out = <Product>[];
  final cats = seedCategories();
  for (final c in cats) {
    final names = _productNames[c.id] ?? ['${c.name} One', '${c.name} Two', '${c.name} Three', '${c.name} Four'];
    for (var i = 0; i < names.length; i++) {
      final name = names[i];
      final pid = '${c.id}-${i + 1}';
      final basePrice = 25000.0 + (i * 17000) + (c.id.hashCode % 7000);
      final old = basePrice + 5000 + (i * 3000);
      final isPop = (i + c.id.length) % 2 == 0;
      final isNew = i == 0;
      final rating = 4.3 + (i * 0.1);
      final brand = _brandIdForCategory(c.id);
      final variants = _variants(c.id, pid, basePrice, name);
      out.add(
        Product(
          id: pid,
          name: name,
          categoryId: c.id,
          brandId: brand,
          price: basePrice,
          oldPrice: i % 3 == 0 ? old : null,
          currency: 'RUB',
          images: [
            _img('$pid-a'),
            _img('$pid-b'),
            _img('$pid-c'),
          ],
          description:
              '$name — премиальная техника категории ${c.name}. Официальная гарантия, быстрая доставка, проверенные поставки. '
              'Идеально подходит для работы, творчества и развлечений.',
          specifications: _specsFor(c.id),
          specificationsMap: _mapFor(c.id, name),
          stockQuantity: i % 7 != 0 ? 6 + i * 3 : 0,
          inStock: i % 7 != 0,
          rating: rating.clamp(0, 5).toDouble(),
          isPopular: isPop,
          isNew: isNew,
          variants: variants,
          sku: '${brand.toUpperCase()}-${pid.toUpperCase()}',
        ),
      );
    }
  }
  return out;
}
