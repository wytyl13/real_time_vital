import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms

class DenoisingAutoencoder(nn.Module):
    """去噪自编码器 - 可处理任意分辨率"""
    
    def __init__(self, channels=3):
        super().__init__()
        
        # 编码器
        self.encoder = nn.Sequential(
            nn.Conv2d(channels, 64, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            
            nn.Conv2d(64, 128, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            
            nn.Conv2d(128, 256, 3, padding=1),
            nn.ReLU(),
        )
        
        # 解码器
        self.decoder = nn.Sequential(
            nn.Conv2d(256, 128, 3, padding=1),
            nn.ReLU(),
            nn.Upsample(scale_factor=2),
            
            nn.Conv2d(128, 64, 3, padding=1),
            nn.ReLU(),
            nn.Upsample(scale_factor=2),
            
            nn.Conv2d(64, channels, 3, padding=1),
            nn.Tanh(),
        )
    
    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded


class ImageDataset(Dataset):
    """图像数据集"""
    def __init__(self, image_paths, size=(256, 256), noise_level=0.3):
        self.image_paths = image_paths
        self.size = size
        self.noise_level = noise_level
        
        self.transform = transforms.Compose([
            transforms.Resize(size),
            transforms.ToTensor(),
            transforms.Normalize([0.5]*3, [0.5]*3)
        ])
    
    def __len__(self):
        return len(self.image_paths)
    
    def __getitem__(self, idx):
        img = Image.open(self.image_paths[idx]).convert('RGB')
        clean = self.transform(img)
        
        # 添加噪声
        noise = torch.randn_like(clean) * self.noise_level
        noisy = torch.clamp(clean + noise, -1, 1)
        
        return noisy, clean


def train_autoencoder(image_paths, epochs=50, batch_size=4):
    """训练自编码器"""
    print("\n" + "="*70)
    print("【训练去噪自编码器】")
    print("="*70 + "\n")
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"使用设备: {device}")
    
    # 数据加载
    dataset = ImageDataset(image_paths, size=(256, 256))
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    # 模型
    model = DenoisingAutoencoder(channels=3).to(device)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # 训练
    for epoch in range(epochs):
        total_loss = 0
        for noisy, clean in dataloader:
            noisy, clean = noisy.to(device), clean.to(device)
            
            # 前向传播
            output = model(noisy)
            loss = criterion(output, clean)
            
            # 反向传播
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / len(dataloader)
        print(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.4f}")
    
    # 保存模型
    torch.save(model.state_dict(), 'denoising_autoencoder.pth')
    print("\n✅ 模型已保存: denoising_autoencoder.pth")
    
    return model


def test_autoencoder(model, image_path, size=(256, 256)):
    """测试自编码器"""
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.eval()
    
    # 加载图像
    transform = transforms.Compose([
        transforms.Resize(size),
        transforms.ToTensor(),
        transforms.Normalize([0.5]*3, [0.5]*3)
    ])
    
    img = Image.open(image_path).convert('RGB')
    original = np.array(img.resize(size))
    clean = transform(img).unsqueeze(0).to(device)
    
    # 添加噪声
    noisy = clean + torch.randn_like(clean) * 0.3
    noisy = torch.clamp(noisy, -1, 1)
    
    # 恢复
    with torch.no_grad():
        recovered = model(noisy)
    
    # 转换为numpy
    def to_numpy(tensor):
        img = tensor.cpu().squeeze().permute(1, 2, 0).numpy()
        img = (img + 1) / 2  # 反归一化
        return np.clip(img, 0, 1)
    
    noisy_np = to_numpy(noisy)
    recovered_np = to_numpy(recovered)
    
    # 可视化
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    axes[0].imshow(original)
    axes[0].set_title(f'原始图像 ({size[0]}×{size[1]})', fontsize=12)
    axes[0].axis('off')
    
    axes[1].imshow(noisy_np)
    axes[1].set_title('添加噪声', fontsize=12)
    axes[1].axis('off')
    
    axes[2].imshow(recovered_np)
    axes[2].set_title('自编码器恢复', fontsize=12)
    axes[2].axis('off')
    
    plt.suptitle('去噪自编码器 - 高分辨率图像处理', fontsize=14)
    plt.tight_layout()
    plt.savefig(f'autoencoder_{size[0]}x{size[1]}.png', dpi=150)
    plt.show()


if __name__ == '__main__':
    image_paths = ['1.jpg', '2.jpg', '3.jpg']
    
    # 训练
    model = train_autoencoder(image_paths, epochs=50)
    
    # 测试
    test_autoencoder(model, '1.jpg', size=(256, 256))
    test_autoencoder(model, '1.jpg', size=(512, 512))  # 更高分辨率