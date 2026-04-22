import 'package:equatable/equatable.dart';

class BannerSlide extends Equatable {
  const BannerSlide({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.imageUrl,
    this.deepLink,
  });

  final String id;
  final String title;
  final String subtitle;
  final String imageUrl;
  final String? deepLink;

  factory BannerSlide.fromJson(Map<String, dynamic> json) => BannerSlide(
        id: json['id'] as String,
        title: json['title'] as String,
        subtitle: json['subtitle'] as String,
        imageUrl: json['imageUrl'] as String,
        deepLink: json['deepLink'] as String?,
      );

  @override
  List<Object?> get props => [id, title, subtitle, imageUrl, deepLink];
}
