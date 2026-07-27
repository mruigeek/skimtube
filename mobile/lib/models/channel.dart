class ChannelModel {
  final int id;
  final String channelId;
  final String name;
  final String createdAt;

  ChannelModel({
    required this.id,
    required this.channelId,
    required this.name,
    required this.createdAt,
  });

  factory ChannelModel.fromJson(Map<String, dynamic> json) {
    return ChannelModel(
      id: json['id'] ?? 0,
      channelId: json['channel_id'] ?? '',
      name: json['name'] ?? '',
      createdAt: json['created_at'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'channel_id': channelId,
      'name': name,
      'created_at': createdAt,
    };
  }
}
