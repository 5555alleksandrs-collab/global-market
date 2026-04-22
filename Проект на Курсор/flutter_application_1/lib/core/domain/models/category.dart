import 'package:equatable/equatable.dart';

class Category extends Equatable {
  const Category({
    required this.id,
    required this.name,
    this.subtitle,
    this.iconName,
  });

  final String id;
  final String name;
  final String? subtitle;

  /// Имя Material icon для UI (опционально).
  final String? iconName;

  factory Category.fromJson(Map<String, dynamic> json) => Category(
        id: json['id'] as String,
        name: json['name'] as String,
        subtitle: json['subtitle'] as String?,
        iconName: json['iconName'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'subtitle': subtitle,
        'iconName': iconName,
      };

  @override
  List<Object?> get props => [id, name, subtitle, iconName];
}
